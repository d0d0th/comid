from tqdm import tqdm
from datetime import datetime
import pandas as pd
import os
import json


class Explorer:
    """
    Class to explore the dataset
    """

    def __init__(self, posts):
        self.posts = posts
        self.threads_stats = dict()
        self.authors_stats = dict()
        self.thread_replies = dict()
        self._thread_authors = dict()
        self.df_interval_activity = pd.DataFrame([])
        self.thread_activity = dict()

        oc_list = [k for k in posts.keys() if 'parent_id' not in posts[k]]
        for oc in tqdm(oc_list, "Processing statistics"):
            self._proc_thread(oc, oc)

    def _proc_thread(self, post_id, oc):
        '''
        Method to process the threads statistics
        '''
        post = self.posts[post_id]
        author_id = post['author_id']

        #threads stats
        if oc not in self.threads_stats:
            self.threads_stats[oc] = {
                'number_ofposts': 0,
                'author_count': 0,
                'posts_without_author_count': 0
            }
        self.threads_stats[oc]['number_ofposts'] += 1

        # author stats
        if oc not in self._thread_authors:
            self._thread_authors[oc] = set()

        if author_id is None:
            self.threads_stats[oc]['posts_without_author_count'] += 1
        else:
            if author_id not in self.authors_stats:
                self.authors_stats[author_id] = list()
            self.authors_stats[author_id].append((post_id, oc))
            if author_id not in self._thread_authors[oc]:
                self.threads_stats[oc]['author_count'] += 1
                self._thread_authors[oc].add(author_id)

        if 'replies' in post:
            #replies list
            if oc not in self.thread_replies:
                self.thread_replies[oc] = []
            if post_id != oc:
                self.thread_replies[oc].append(post_id)

            # recursive call
            for reply in post['replies']:
                self._proc_thread(reply, oc)

    def data_summary(self):
        """
        The function prints basic information about the loaded data:

        Number of OCs
        Number of OCs without content
        Number of OCs without author
        Number of comments/replies
        Number of comments/replies without content
        Number of comments/replies without author
        """
        oc = 0
        comments = 0
        oc_no_author = 0
        comments_no_author = 0
        oc_no_content = 0
        comments_no_content = 0
        for post in self.posts.values():
            if 'parent_id' not in post:
                oc += 1
                if post['author_id'] is None:
                    oc_no_author += 1
                if post['selftext'] in ["[removed]", "[deleted]"]:
                    oc_no_content += 1
            else:
                comments += 1
                if post['author_id'] is None:
                    comments_no_author += 1
                if post['full_text'] in ["[removed]", "[deleted]"]:
                    comments_no_content += 1
        print("Number of posts: ", len(self.posts))
        if oc > 0:
            print("Number of OCs:", oc)
            print("Number of OCs without content:", oc_no_content, "(" + str(round(100 * oc_no_content / oc, 2)) + "%)")
            print("Number of OCs without author:", oc_no_author, "(" + str(round(100 * oc_no_author / oc, 2)) + "%)")
        if comments > 0:
            print("Number of comments/replies:", comments)
            print("Number of comments/replies: without content:", comments_no_content,
                  "(" + str(round(100 * comments_no_content / comments, 2)) + "%)")
            print("Number of comments/replies: without author:", comments_no_author,
                  "(" + str(round(100 * comments_no_author / comments, 2)) + "%)")

    def thread_interval_activity(self, period_type):
        '''
        Method to calculate the interval_activity
        ::param period_type: The period to group the posts. Can be 'd' for days, 'w' for weeks,
        'f' for fortnight, 'm' for months, 'q' for quarters or 'y' for years
        '''

        periods_list = sorted(set([self._period_key(v['created'], period_type) for v in self.posts.values()]))
        periods_dict = {item: index + 1 for index, item in enumerate(periods_list)}
        oc_list = [k for k in self.posts.keys() if 'parent_id' not in self.posts[k]]
        data = [[0 for i in range(len(periods_list) + 1)] for j in range(len(oc_list))]

        for row_index, oc_id in tqdm(enumerate(oc_list), "Processing interval activity"):
            data[row_index][0] = oc_id
            self._proc_interval(oc_id, oc_id, data, row_index, self.posts, periods_dict, period_type)
        header = ['thread_id'] + periods_list
        self.df_interval_activity = pd.DataFrame(data, columns=header)
        self.df_interval_activity.set_index('thread_id', inplace=True)

    def _proc_interval(self, post_id,oc_id, data, row_index, posts, periods_dict, period_type):
        '''
        Recursively process the interval activity
        '''
        post = posts[post_id]
        period = self._period_key(post['created'],period_type)
        data[row_index][periods_dict[period]] += 1
        if period not in self.thread_activity:
            self.thread_activity[period] = dict()
        if oc_id not in self.thread_activity[period]:
            self.thread_activity[period][oc_id] = []
        self.thread_activity[period][oc_id].append(post_id)

        if 'replies' in post:
            for reply in post['replies']:
                self._proc_interval(reply, oc_id, data, row_index, posts, periods_dict, period_type)

    def export_data(self, save_path=""):
        '''
        Method to export the data
        :param save_path: The path to save the corpus file. If not informed will be saved in current default path.
        '''
        timestamp = str(round(datetime.timestamp(datetime.now())))
        self._dump_json(self.threads_stats, "threads_stats_" + timestamp + ".json", save_path)
        self._dump_json(self.authors_stats, "authors_stats_" + timestamp + ".json", save_path)
        self._dump_json(self.thread_replies, "thread_replies_" + timestamp + ".json", save_path)
        self._dump_json(self.thread_activity, "thread_activity_" + timestamp + ".json", save_path)
        self._dump_dataframe(self.df_interval_activity, "interval_activity_" + timestamp + ".csv", save_path)

    def _dump_json(self, obj, file_name,save_path):
        '''
        Method to dump the json file
        '''
        file = file_name if not save_path else os.path.join(save_path, file_name)
        with open(file, "w", encoding="utf-8") as outfile:
            json.dump(obj, outfile)
        print("Saved file " + file)

    def _dump_dataframe(self, df, file_name, save_path):
        '''
        Method to dump the dataframe
        '''
        file = file_name if not save_path else os.path.join(save_path, file_name)
        df.to_csv(file, index=True)
        print("Saved file " + file)

    @staticmethod
    def _period_key(timestamp, period_type):
        """
        Retrieve the period group label given a timestamp and period type
        :param timestamp: The utc timestamp
        :param period_type: The period to group the topics. Can be 'd' for days, 'w' for weeks,
        'f' for fortnight, 'm' for months, 'q' for quarters or 'y' for years
        :return: The period group label
        """
        dt = datetime.fromtimestamp(timestamp)
        per = period_type.lower()
        if per == "d":
            period_key = dt.strftime('%Y-%m-%d')
        elif per == "w":
            period_key = dt.strftime('%Y-%W')
        elif per == "m":
            period_key = dt.strftime('%Y-%m')
        elif per == "f":
            period_key = dt.strftime('%Y-%m') + ('-F1' if dt.day < 15 else '-F2')
        elif per == "q":
            period_key = dt.strftime('%Y')
            if dt.month < 4:
                period_key += '-Q1'
            elif dt.month < 7:
                period_key += '-Q2'
            elif dt.month < 10:
                period_key += '-Q3'
            else:
                period_key += '-Q4'
        elif per == "y":
            period_key = dt.strftime('%Y')
        else:
            raise Exception("Invalid period_type. Available options are 'd' for days, 'w' for weeks,"
                            "'f' for fortnight, 'm' for months, 'q' for quarters or "
                            "'y' for years")
        return period_key





