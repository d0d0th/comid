import json
import random
import os
from datetime import datetime
import redditcleaner as rc
import contractions
import nltk
import re
import spacy
from tqdm import tqdm
from nltk.stem.snowball import SnowballStemmer
import csv
import pandas as pd
import pickle
import numpy as np
from itertools import chain
import math


class Comid:
    """
    The Comid class
    """

    def __init__(self):
        self.words_map = None
        self.corpus = None
        self.corpus_reduced = None
        self.posts = None
        self.stopwords = None
        self.df_clusters = None
        self.df_topics = None
        self.df_periods = None

    def load_json_files(self, files=None, folder=None):
        """
        Load json files as comid dict object
        :param files: List of files to be loaded. Example ['file1.json','file2.json','file3.json']. Can be omitted if
            folder parameter informed.
        :param folder: Path of the folder where the files to be loaded are located. If informed, all files in the folder
            will be loaded.
        :return: None
        """
        self.posts = dict()
        if not folder and not files:
            raise Exception("json files path array or folder path need to be informed")
        if folder and files:
            raise Exception(
                "Inform just one of parameters files path array or foder path. You can't inform both at same time.")
        if not files:
            files = [f for f in os.listdir(folder)]
            # files = [f for f in os.listdir(folder) if '.json']

        for file in tqdm(files, desc="Loading...", position=0):
            with open(file) as f:
                data = json.load(f)
                for d in data:
                    text = ''
                    if 'title' in d:
                        text += d['title'] + " "
                    if 'selftext' in d:
                        text += d['selftext']
                    if 'body' in d:
                        text += d['body']
                    d['full_text'] = text

                my_dict = dict(map(lambda x: (x['id'], x), data))
                self.posts.update(my_dict)

    def generate_corpus(self, use_lemmas=True, include_comments=False):
        """
        Generates the corpus with the list of tokens from each document
        :param use_lemmas: If True will lemmatize the tokens, if false will stemm the tokens. The default is use_lemmas
            set as True
        :param include_comments: Informs if will include te texts of the comments in document.
        :return: None
        """
        oc_dict = dict(filter(lambda e: 'parent_id' not in e[1] and e[1]['selftext'] not in ["[removed]", "[deleted]"],
                              tqdm(self.posts.items(), desc="Filtering content")))

        if include_comments:
            filtered_comments = dict(
                filter(lambda e: 'parent_id' in e[1] and e[1]['parent_id'] in oc_dict.keys()
                                 and e[1]['full_text'] not in ["[removed]", "[deleted]"],
                       tqdm(self.posts.items(), desc="Filtering comments")))

            for key in tqdm(filtered_comments.keys(), desc="Adding comments"):
                oc_dict[filtered_comments[key]['parent_id']]['full_text'] += " " + filtered_comments[key]['full_text']

        oc = list(
            map(lambda e: [e[0], rc.clean(e[1]['full_text'])], tqdm(oc_dict.items(), desc="Cleaning reddit marks")))

        oc = list(map(lambda e: [e[0], contractions.fix(e[1]).lower()], tqdm(oc, desc="Apping contractions")))
        oc = list(
            map(lambda e: [e[0], re.sub(r'[\W\d_]+', ' ', e[1]).split()], tqdm(oc, desc="Removing non-aplhanumerics")))

        nltk.download('stopwords')
        self.stopwords = nltk.corpus.stopwords.words('english')
        oc = list(map(lambda e: [e[0], self._filter_stopwords(e[1])], tqdm(oc, desc="Filtering stopwords")))

        # !python -m spacy download en
        if use_lemmas:
            nlp = spacy.load('en_core_web_sm')
            oc = list(map(lambda e: [e[0], self._lemmatize(e[1], nlp)], tqdm(oc, desc="Lemmatizing")))
        else:
            stemmer = SnowballStemmer(language='english')
            oc = list(map(lambda e: [e[0], self._steems(e[1], stemmer)], tqdm(oc, desc="Stemming")))

        self.corpus = dict(
            map(lambda e: (e[0], self._filter_small_words(e[1])), tqdm(oc, desc="Filtering small words")))

    def reduce_corpus(self, target_size=6000, optimize_num_interactions=True, min_op_length=0,
                      min_num_interactions=0):
        """
        Reduce the corpus closest to a target size. The function find a minimal value for number of interactions
        (the total number of comments and replies in original post) or the op length (number of tokens in original
        post) and reduce the corpus removing all documents that not satisfact the minimal value calculated.

        :param target_size: The target corpus size.
        :param optimize_num_interactions: If True reduce the corpus calculating a mínimal value for number of
        interactions (the total number of comments and replies in original post). If False reduce the corpus calculating
        a mínimal value for op length (number of tokens in original post)
        :param min_op_length: The minimal op lenght (number of tokens in original post) to filter the corpus. Only have
        effect if optimize_num_interactions is True.
        :param min_num_interactions: The minimal number of interactions (the total number of comments and replies in
        original post) to filter the corpus. Only have effect if optimize_num_interactions is False.
        :return: None
        """

        corpus = self.corpus

        if target_size <= 0:
            raise Exception("Corpus size must be higher than zero")

        corpus_dict = {doc: {'tokens': corpus[doc],
                             'num_interactions': self.posts[doc]['num_comments'],
                             'op_length': len(corpus[doc])} for doc in corpus}

        if optimize_num_interactions:
            corpus_dict = dict(filter(lambda x: x[1]['op_length'] >= min_op_length, corpus_dict.items()))
            minimize = [el["num_interactions"] for el in corpus_dict.values()]
        else:
            corpus_dict = dict(filter(lambda x: x[1]['num_interactions'] >= min_num_interactions, corpus_dict.items()))
            minimize = [el["op_length"] for el in corpus_dict.values()]

        if target_size > len(corpus_dict):
            target_size = len(corpus_dict)

        minimize.sort(reverse=True)
        # The point of cut
        cut = minimize[target_size - 1]
        # looking for the closest minimum value
        count_pos = 0
        index_pos = target_size - 1
        while minimize[index_pos] == cut and index_pos < len(minimize) - 1:
            count_pos += 1
            index_pos += 1
        count_pre = 0
        index_pre = target_size - 1
        while minimize[index_pre] == cut and index_pre > 0:
            count_pre += 1
            index_pre -= 1
        min_value = minimize[index_pre if count_pre < count_pos else index_pos]

        if optimize_num_interactions:
            corpus_dict = dict(filter(lambda x: x[1]['num_interactions'] >= min_value, corpus_dict.items()))
        else:
            corpus_dict = dict(filter(lambda x: x[1]['op_length'] >= min_value, corpus_dict.items()))

        self.corpus_reduced = {el[0]: el[1]['tokens'] for el in corpus_dict.items()}

    def save(self, save_path="", file_name=""):
        """
        Save the Comid object with current state and data
        :param save_path: The path to save the comid file. If not informed will be saved in current default path.
        :param file_name: The comid file name. If not informed will generate a file with the pattern name
            "comid_"+UTC_TIMESTAMP+".pickle"
        :return: None
        """
        if not file_name:
            now = datetime.now()
            file_name = "comid_" + str(round(datetime.timestamp(now))) + ".pickle"
        file = file_name if not save_path else os.path.join(save_path, file_name)

        with open(file, 'wb') as f:
            pickle.dump(self, f)

        print("Saved file " + file)

    @classmethod
    def load(cls, file):
        """
        Load the comid object from a saved file
        :param file: The comid object file to be loaded. Can be used with relative or full path.
        :return: The comid object
        """
        with open(file, 'rb') as f:
            return pickle.load(f)

    def save_corpus(self, reduced=False, save_path="", file_name=""):
        """
        Save the corpus as a json file.
        :param reduced: If True will save the reduced corpus, if False will save the full corpus
        :param save_path: The path to save the corpus file. If not informed will be saved in current default path.
        :param file_name: The corpus file name. If not informed will generate a file with the pattern name
            "corpus_"+UTC_TIMESTAMP+".json"
        :return: None
        """

        corpus = self.corpus_reduced if reduced else self.corpus

        if not file_name:
            now = datetime.now()
            file_name = "corpus_" + str(round(datetime.timestamp(now))) + ".json"
        file = file_name if not save_path else os.path.join(save_path, file_name)

        with open(file, "w", encoding="utf-8") as outfile:
            json.dump(corpus, outfile)
        print("Saved file " + file)

    def load_corpus(self, file):
        """
        Load the corpus json file
        :param file: The corpus file to be loaded. Can be used with relative or full path.
        :return: None
        """
        with open(file, "r", encoding="utf-8") as f:
            self.corpus = json.load(f)

    def load_clusters_file(self, file):
        """
        Load the clusters file and create the df_cluster dataframe
        :param file: The csv file path + name to be loaded. Can be used relative or full path.
        :return:
        """
        self.df_clusters = pd.read_csv(file)

    def print_cluster_samples(self, cluster, n_samples=10, max_depth=0):
        """
        Print random samples from a cluster
        :param cluster:  The cluster to analyze
        :param max_depth: The maximum depth of replies to retrieve given a doc id. If max_depth = 0 will retrieve only
        the OC
        :param n_samples: The number of samples. Default is 10
        :return: None
        """

        ids = random.sample(list(self.df_clusters[cluster].dropna().to_list()), n_samples)
        index = 0
        for el in ids:
            index += 1
            print("Sample ", index)
            print(self.retrieve_conversation(el, max_depth))
            print("\n" + "##############################################")

    def save_clusters_summary(self, save_path="", file_name=""):
        """
        Save the cluster csv summary file
        :param save_path: The path to save the file. If not informed will be saved in current default path.
        :param file_name: The cluster stats file name. If not informed will generate a file with the pattern
            "clusters_summary_"+UTC_TIMESTAMP+".csv"
        :return: None
        """
        total = 0
        header = ['Cluster', 'Num Docs', 'Percent', 'Topic']
        data = []
        for col in self.df_clusters.columns:
            n = self.df_clusters[col].count()
            data.append([col, n, 0, ''])
            total += n
        for row in data:
            row[2] = round(100 * row[1] / total, 2)

        if not file_name:
            now = datetime.now()
            file_name = "clusters_summary_" + str(round(datetime.timestamp(now))) + ".csv"
        file = file_name if not save_path else os.path.join(save_path, file_name)

        with open(file, 'w', encoding='UTF8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(data)
        print("Saved file " + file)

    def build_topics(self, topics_file=None, min_percent=10):
        """
        Creates the topics conversation dataframe. The dataframe can be created from a csv file with the topics
        anotation.
        :param topics_file: The label csv file. When informed it will be considered only the topics that have informed
        in file.
        :param min_percent: The minimal percent of documents in a cluster to consider the cluster as a topic in
        dataframe. If label file informed, this parameter will be ignored.
        :return: None
        """
        topics = dict()
        if topics_file:
            with open(topics_file, 'r') as file:
                csvreader = csv.reader(file)
                header = next(csvreader)
                ind_cluster = header.index("Cluster")
                ind_topic = header.index("Topic")
                for row in csvreader:
                    if str(row[ind_topic]).strip():
                        topics[row[ind_cluster]] = row[ind_topic].strip()
        else:
            percents = []
            total = 0
            for col in self.df_clusters.columns:
                n = self.df_clusters[col].count()
                percents.append([col, n])
                total += n
            for row in percents:
                if round(100 * row[1] / total, 2) >= min_percent:
                    topics[row[0]] = row[0]

        data = []
        for cluster in tqdm(topics, desc="Building topics dataframe..."):
            docs = self.df_clusters[cluster]
            for doc in docs[docs.notnull()]:
                post = self.posts[doc]
                created_at = datetime.fromtimestamp(post['created']).strftime('%Y-%m-%d %H:%M:%S')
                data.append(
                    [doc, topics[cluster], post['author_id'], 0, '', created_at, post['created'], post['full_text'],
                     doc])
                if 'replies' in post:
                    for reply in post['replies']:
                        self._proc_replies(reply, data, doc, topics[cluster])
                if 'comments' in post:
                    for reply in post['comments']:
                        self._proc_replies(reply, data, doc, topics[cluster])
        self.df_topics = pd.DataFrame(data, columns=['id', 'topic', 'author_id', 'depth', 'parent_id', 'created_at',
                                                     'created_utc', 'fulltext', 'oc'])
        self.df_topics = self.df_topics.set_index('id')

        return

    @staticmethod
    def _retrieve_period(timestamp, period_type):
        """
        Retrieve the period group label given a timestamp and period type
        :param timestamp: The utc timestamp
        :param period_type: The period to group the topics. Can be 'd' for days, 'w' for weeks, 'm' for months and
        'y' for years
        :return:
        """
        dt = datetime.fromtimestamp(timestamp)
        per = period_type.lower()
        if per == "d":
            period_key = dt.strftime('%Y-%m-%d')
        elif per == "w":
            period_key = dt.strftime('%Y-%W')
        elif per == "m":
            period_key = dt.strftime('%Y-%m')
        elif per == "y":
            period_key = dt.strftime('%Y')
        else:
            period_key = None
        return period_key

    def group_by_period(self, period_type="m"):
        """
        Group the topics in a given period updating the period column in df_topics and generating the df_periods
        :param period_type: The period to group the topics. Can be 'd' for days, 'w' for weeks, 'm' for months and
        'y' for years
        :return: None
        """
        per = period_type.lower()
        if per == "d":
            period_description = "days"
        elif per == "w":
            period_description = "weeks"
        elif per == "m":
            period_description = "months"
        elif per == "y":
            period_description = "years"
        else:
            raise Exception("Parameter period invalid. Available options: 'd','w','m' or 'y'")

        tqdm.pandas(desc="periods")
        self.df_topics['period'] = self.df_topics['created_utc'].progress_apply(
            lambda e: self._retrieve_period(e, period_type))
        tqdm.pandas(desc="tokens")
        self.df_topics['tokenized'] = self.df_topics.progress_apply(
            lambda e: self.corpus[e.name] if e.name in self.corpus else [], axis=1)
        data = []

        # x
        self.words_idx = {word: i for i, word in enumerate(set(chain.from_iterable(self.corpus.values())))}
        # Y
        self.topics_idx = {topic: i for i, topic in
                           enumerate(self.df_topics[~self.df_topics['topic'].isnull()]['topic'].unique().tolist())}
        # Z
        self.periods_idx = {period: i for i, period in enumerate(self.df_topics['period'].unique().tolist())}

        self.periods_array = np.zeros((len(self.words_idx), len(self.topics_idx), len(self.periods_idx)), dtype=int)

        for period in tqdm(sorted(self.df_topics['period'].unique().tolist()), "Grouping by " + period_description):
            df_period = self.df_topics[self.df_topics['period'] == period]

            '''
            self.periods_counter[period] = [0, {}]
            '''
            z = self.periods_idx[period]
            for topic in df_period[~df_period['topic'].isnull()]['topic'].unique().tolist():

                df_topic_period = df_period[df_period['topic'] == topic]
                new_threads = df_topic_period[df_topic_period['depth'] == 0].shape[0]
                replies = df_topic_period[df_topic_period['depth'] > 0].shape[0]

                words_topic = df_topic_period.tokenized.explode().dropna().tolist()
                y = self.topics_idx[topic]

                for word in set(words_topic):
                    x = self.words_idx[word]
                    self.periods_array[x, y, z] += words_topic.count(word)

                if per == "d":
                    data.append(
                        {
                            "period": period,
                            "year": period[0:4],
                            "month": period[5:7],
                            "day": period[8:10],
                            "topic": topic,
                            "new_threads": new_threads,
                            "replies": replies
                        }
                    )
                elif per == "w":
                    data.append(
                        {
                            "period": period,
                            "year": period[0:4],
                            "week": period[5:7],
                            "topic": topic,
                            "new_threads": new_threads,
                            "replies": replies
                        }
                    )
                elif per == "m":
                    data.append(
                        {
                            "period": period,
                            "year": period[0:4],
                            "month": period[5:7],
                            "topic": topic,
                            "new_threads": new_threads,
                            "replies": replies
                        }
                    )
                elif per == "y":
                    data.append(
                        {
                            "period": period,
                            "year": period,
                            "topic": topic,
                            "new_threads": new_threads,
                            "replies": replies
                        }
                    )
        self.df_periods = pd.DataFrame(data)
        return

    def distinctiveness(self, topic, period):
        z = self.periods_idx[period]
        y = self.topics_idx[topic]
        count = 0
        sum_specificity = 0
        for x in np.where(self.periods_array[:, y, z] > 0)[0]:
            sum_specificity += self.specificty_by_index(x, y, z)
            count += 1
        if count == 0:
            raise Exception("It isn't possible find the distinctiveness for topic " + topic + " at " + period)
        return sum_specificity / count

    def dynamicity(self, topic, period):
        z = self.periods_idx[period]
        y = self.topics_idx[topic]
        count = 0
        sum_volatility = 0
        for x in np.where(self.periods_array[:, y, z] > 0)[0]:
            sum_volatility += self.volatility_by_index(x, y, z)
            count += 1
        if count == 0:
            raise Exception("It isn't possible find the dynamicity for topic " + topic + " at " + period)
        return sum_volatility / count

    def specificity(self, word, topic, period):
        z = self.periods_idx[period]
        y = self.topics_idx[topic]
        x = self.words_idx[word]

        return self.specificty_by_index(x, y, z)

    def specificty_by_index(self, x, y, z):
        a1 = self.periods_array[x, y, z]
        b1 = self.periods_array[:, y, z].sum()
        a2 = self.periods_array[x, :, z].sum()
        b2 = self.periods_array[:, :, z].sum()
        if 0 in (a1, b1, b2, b2):
            raise Exception(
                "It isn't possible find the specificity for (x, y, z) : (" + str(x) + ", " + str(y) + ", " + str(
                    z) + ")")
        p_topic = a1 / b1
        p_all_topics = a2 / b2
        return math.log10(p_topic / p_all_topics)

    def volatility(self, word, topic, period):
        z = self.periods_idx[period]
        y = self.topics_idx[topic]
        x = self.words_idx[word]

        return self.volatility_by_index(x, y, z)

    def volatility_by_index(self, x, y, z):
        a1 = self.periods_array[x, y, z]
        b1 = self.periods_array[:, y, z].sum()
        a2 = self.periods_array[x, y, :].sum()
        b2 = self.periods_array[:, y, :].sum()
        if 0 in (a1, b1, b2, b2):
            raise Exception(
                "It isn't possible find the volatility for (x, y, z) : (" + str(x) + ", " + str(y) + ", " + str(
                    z) + ")")
        p_topic = a1 / b1
        p_topic_all_periods = a2 / b2

        return math.log10(p_topic / p_topic_all_periods)

    def discrepancy_of_interactions(self, topic, period):
        df_filtered_topic = self.df_periods[self.df_periods['topic'] == topic]
        if len(df_filtered_topic) < 1:
            raise Exception("Invalid topic " + topic)
        df_filtered_period = self.df_periods[self.df_periods['period'] == period]
        if len(df_filtered_period) < 1:
            raise Exception("Invalid period " + period)
        a1 = df_filtered_period[df_filtered_period['topic'] == topic]['replies'].sum()
        b1 = df_filtered_period['replies'].sum()
        a2 = df_filtered_topic['replies'].sum()
        b2 = self.df_periods['replies'].sum()
        if 0 in (a1, b1, b2, b2):
            raise Exception("It isn't possible to find the discrepancy for the topic " + topic + " in the period "+period)

        p_topic_period = a1 / b1
        p_topic_all_periods = a2 / b2
        return math.log10(p_topic_period / p_topic_all_periods)

    def _proc_replies(self, doc_id, data, oc, topic):
        """
        Internal recursive function to proc replies from a given post id
        :param doc_id: The post (submission, commento or reply) id
        :param data: the data list
        :param oc: The oc id
        :param topic: The OC topic
        :return: The data list
        """
        post = self.posts[doc_id]
        if post['full_text'] not in ["[removed]", "[deleted]"]:
            if 'replies' in post:
                for reply in post['replies']:
                    self._proc_replies(reply, data, oc, topic)
            created_at = datetime.fromtimestamp(post['created']).strftime('%Y-%m-%d %H:%M:%S')
            data.append([post['id'], topic, post['author_id'], post['depth'], post['parent_id'], created_at,
                         post['created'], post['full_text'], oc])

        # doc_id author_id cluster depth parent_id created fulltext oc_id

    @staticmethod
    def _lemmatize(tokenized_list, nlp):
        """
        Lemmatizes a list of tokens
        :param tokenized_list: The list of tokens to be lemmatized
        :param nlp: The lemmatizer
        :return: The list of lemmatized tokens
        """
        ngrams = list(filter(lambda t: "-" in t, tokenized_list))
        rest = list(filter(lambda t: t not in ngrams, tokenized_list))
        doc = nlp(" ".join(rest))
        return [token.lemma_ for token in doc] + ngrams

    @staticmethod
    def _steems(tokenized_list, stemmer):
        """
        Steems a list of tokens
        :param tokenized_list: The list of tokens to be stemmed
        :param stemmer: The stemmer
        :return: The list of stemmed tokens
        """
        return [stemmer.stem(token) for token in tokenized_list]

    def _filter_stopwords(self, words):
        """
        Filters stop words from a list of words
        :param words: The list of words to be filtered
        :return: The list of filtered words
        """
        return list(filter(lambda word: word not in self.stopwords, words))

    @staticmethod
    def _filter_small_words(words, min_size=3):
        """
        Filters small words from a list of words
        :param words: The list of words to be filtered
        :param min_size: minimum word length. Default is 3
        :return: The list of filtered words
        """
        return list(filter(lambda word: len(word) >= min_size, words))

    def retrieve_conversation(self, doc_id, max_depth=99999, include_author_id=True, include_created=True, level=0):
        """
        Recursive function to retrieve a thread conversation in a flatten text
        :param doc_id: The post id
        :param max_depth: The maximum depth of replies to retrieve given a doc id. If max_depth = 0 will not retrieve
        replies
        :param include_author_id: Informs if the author will be included in text, default is True
        :param include_created: Informs if the post date time will be included, default is True
        :param level: The post level in conversation hierarchy
        :return: The conversation flatten text
        """
        post = self.posts[doc_id]
        text = ""
        if post['full_text'] not in ["[removed]", "[deleted]"]:
            if level > 0:
                tab = "-"
                text += "\n" + tab * level
            if include_created:
                text += datetime.fromtimestamp(post['created']).strftime('%Y-%m-%d %H:%M:%S') + " "
            if include_author_id:
                text += str(post['author_id']) + ": "
            text += post['full_text']

            level += 1
            if level <= max_depth:
                if 'replies' in post:
                    for reply in post['replies']:
                        text += self.retrieve_conversation(reply, max_depth, include_author_id, include_created, level)

        return text
