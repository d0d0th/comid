import time

import prawcore
import datetime as dt
import csv
import praw
from tqdm import tqdm
import os
import json
from comid.pullpush import PullPushApi


class RedditCollector:
    """
    A class to collect a subreddit
    """

    def __init__(self):
        self.ids = list()
        self.es = None
        self.submission_fields = ['all_awardings', 'author', 'author_id', 'author_flair_text', 'created', 'downs',
                                  'id', 'link_flair_text', 'num_comments', 'num_crossposts', 'permalink', 'score',
                                  'selftext', 'subreddit', 'title', 'total_awards_received', 'ups', 'upvote_ratio']
        self.comments_fields = ['all_awardings', 'author', 'author_id', 'author_flair_text', 'body',
                                'controversiality', 'created', 'depth', 'downs', 'id', 'parent_id', 'permalink',
                                'score', 'subreddit', 'total_awards_received', 'ups']
        self.reddit_credentials = {
            'client_id': 'Put your reddit api client id here',
            'client_secret': 'Put your reddit api client secret here',
            'password': 'Put your reddit api password here',
            'user_agent': 'comid RedditCollector',
            'username': 'Put your reddit api username here'
        }

    def search_ids_by_datetime(self, subreddit, start_datetime, end_datetime, file_name=None):
        """
        Searchs ids in pushshift repository by datetime and store the ids list in a text file
        :param subreddit: The subreddit to be collected.
        :param start_datetime: The initial post datatime range to collect
        :param end_datetime: The final post datetime range to collect
        :param file_name: The file to save the ids.
        :return:
        """

        after = int(start_datetime.timestamp())
        api = PullPushApi()
        limit = 1000
        day_count = 24 * 60 * 60
        self.ids = []
        delta = end_datetime- start_datetime
        num_days = int(delta.days) +1

        if not file_name:
            stamp = str(round(dt.datetime.now().timestamp()))
            file_name = subreddit+"_ids_" + stamp + ".csv"

        for _ in tqdm(range(num_days), "Collecting ids by day"):
            before = after + day_count
            submissions = list(
                api.search_submissions(after=after, before=before, sort='desc', subreddit=subreddit, limit=limit))

            for sub in submissions:
                line = sub["id"] + "," + str(sub["created_utc"])
                self.__append_new_line__(file_name, line)
                self.ids.append(sub["id"])
            after = before
        print("Total ids collected:",len(self.ids))
        print("Ids saved in file "+file_name)

    def load_ids_file(self, file_name, id_col_index=0):
        """
        Loads the csv file with the posts ids to collect
        :param file_name: The ids csv file
        :param id_col_index: The column index that is the id. The default is 0.  
        :return: 
        """
        with open(file_name) as csv_file:
            self.ids = list()
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                self.ids.append(row[id_col_index])

    def config_credentials(self, client_id, client_secret, password, username, user_agent='comid'):
        """
        Config Reddit api authentication parameters
        :param client_id: The app client_id.
        :param client_secret: The app client_secret
        :param password: The Reddit user password
        :param username: The Reddit username
        :param user_agent: The user_agent. The default is comid
        :return: None
        """
        self.reddit_credentials['client_id'] = client_id
        self.reddit_credentials['client_secret'] = client_secret
        self.reddit_credentials['password'] = password
        self.reddit_credentials['user_agent'] = user_agent
        self.reddit_credentials['username'] = username


    def __procReplies__(self, replies, file_comments):
        """
        Internal usage.  Recursive method to iterate over comments and replies
        :param replies: The replies instance
        :param file_comments: The comments file.
        :return: 
        """
        ret = list()
        for reply in replies:
            ret.append(reply.id)
            comment = dict()
            for field in self.comments_fields:
                if field == 'author':
                    comment[field] = str(reply.author) if hasattr(reply, 'author') else None
                elif field == 'parent_id':
                    comment[field] = reply.parent_id[3:] if hasattr(reply, 'parent_id') else None
                elif field == 'author_id':
                    comment[field] = reply.author_fullname[3:] if hasattr(reply, 'author_fullname') else None
                elif field == 'subreddit':
                    comment[field] = str(reply.subreddit) if hasattr(reply, 'subreddit') else None
                else:
                    comment[field] = getattr(reply, field, None)

            if hasattr(reply, 'replies'):
                comment['replies'] = self.__procReplies__(reply.replies, file_comments)

            self.__append_json_string__(file_comments, json.dumps(comment))

        return ret

    def donwload_by_ids(self, download_coments=True, ids=None, output_folder=None, max_retries=50):
        """
        Download and sotrethe submissions by ids
        :param download_coments: Informs if will download comments and replies. The default is True.
        :param ids: The list of ids to download
        :param output_folder: The folder to save the submissions.
        :param max_retries: The maximum number of retries to download if a connection error occurs.
        :return: None
        """
        stamp = str(round(dt.datetime.now().timestamp()))
        file_submissions = "submissions_" + stamp+".json"
        file_comments = "comments_" + stamp+".json"
        file_remaining_ids = "remaining_ids_" + stamp+".csv"

        if max_retries < 0:
            raise Exception("max_retries cannot be negative")
        reddit = praw.Reddit(
            client_id=self.reddit_credentials['client_id'],
            client_secret=self.reddit_credentials['client_secret'],
            password=self.reddit_credentials['password'],
            user_agent=self.reddit_credentials['user_agent'],
            username=self.reddit_credentials['username']
        )

        if output_folder:
            if os.path.exists(output_folder):
                raise Exception("output path not exists")
            file_submissions = os.path.join(output_folder, file_submissions)
            file_comments = os.path.join(output_folder, file_comments)
            file_remaining_ids = os.path.join(output_folder, file_remaining_ids)

        print(reddit.user.me())
        start = dt.datetime.now()
        if not ids:
            ids = self.ids

        pbar = tqdm(range(len(ids)))
        for i in pbar:
            self.__write_remaining_ids(file_remaining_ids,ids[i:])
            doc_id = ids[i]

            retry = True
            count_retry = 0
            last_exception = None
            pbar.set_description(f"Downloading O.C. {doc_id}")

            while retry:
                if count_retry > max_retries:
                    raise last_exception
                try:
                    submission = reddit.submission(doc_id)
                    doc = dict()

                    for field in self.submission_fields:
                        if field == 'author':
                            doc[field] = str(submission.author) if hasattr(submission, 'comments') else None
                        elif field == 'author_id':
                            doc[field] = submission.author_fullname[3:] if hasattr(submission,
                                                                                   'author_fullname') else None
                        elif field == 'subreddit':
                            doc[field] = str(submission.subreddit) if hasattr(submission, 'subreddit') else None
                        else:
                            doc[field] = getattr(submission, field, None)

                    if download_coments:
                        if hasattr(submission, 'comments'):
                            submission.comments.replace_more(limit=None)
                            doc['replies'] = self.__procReplies__(submission.comments, file_comments)

                    retry = False
                    self.__append_json_string__(file_submissions, json.dumps(doc))

                except prawcore.exceptions.ServerError as e:
                    # wait for 30 seconds since sending more requests to overloaded server
                    last_exception = e
                    print("Reddit server response error:", e.response.status_code)
                    print("Waiting 30 seconds to retry the request")
                    count_retry += 1
                    time.sleep(30)
                    print("Retrying submission ", doc_id, "attempts retry count: ", count_retry)

        print("saved submissions file "+file_submissions)
        print("saved comments file " + file_comments)
        print('Download completed. Started at ', start,'finished at ', dt.datetime.now())
        os.remove(file_remaining_ids)

    @staticmethod
    def __append_new_line__(file_name, text_to_append):
        """
        Internal usage. Append a text as a new line at the end of file
        :param file_name: The file
        :param text_to_append: The text
        :return:
        """
        with open(file_name, "a+") as outfile:
            outfile.seek(0)
            data = outfile.read(100)
            if len(data) > 0:
                outfile.write("\n")
            outfile.write(text_to_append)

    @staticmethod
    def __append_json_string__(file_name, json_text):
        """
        Internal usage. Append a string of json in a jon file
        :param file_name: The file name
        :param json_text: The json string
        :return:
        """
        if os.path.isfile(file_name):
            with open(file_name, "ab+") as outfile:
                outfile.seek(-1, 2)
                outfile.truncate()
                text = ","+json_text + "]"
                outfile.write(text.encode())
        else:
            with open(file_name, "ab+") as outfile:
                text = "["+json_text + "]"
                outfile.write(text.encode())

    @staticmethod
    def __write_remaining_ids(file_name, ids):
        with open(file_name, "w") as outfile:
            ids_2d = [[id] for id in ids]
            csv_writer = csv.writer(outfile)
            csv_writer.writerows(ids_2d)

    """
    def deprecated_downlad_by_datetime(self, subreddit, start_datetime, end_datetime=None,download_coments=True,
                            output_folder=None, max_retries=50,after=None):
        
        Download submissions in a datetime range
        :param subreddit: The subreddit to download
        :param start_datetime: The initial post datatime range (inclusive) to collect
        :param end_datetime: The initial final datatime range (not inclusive) to collect. If not informed, will consider
        the current datetime.
        :param download_coments:  Informs if will download comments and replies. The default is True.
         :param output_folder: The folder to save the submissions.
        :param max_retries: The maximum number of retries to download if a connection error occurs.
        :param after: If informed, will consider only de ids oldest from after.
        :return:
        
        if not end_datetime:
            end_datetime =  dt.datetime.now()
        start_utc = start_datetime.timestamp()
        end_utc = end_datetime.timestamp()
        start = dt.datetime.now()
        stamp = str(round(dt.datetime.now().timestamp()))
        file_submissions = "submissions_" + stamp + ".json"
        file_comments = "comments_" + stamp + ".json"

        if max_retries < 0:
            raise Exception("max_retries cannot be negative")
        reddit = praw.Reddit(
            client_id=self.reddit_credentials['client_id'],
            client_secret=self.reddit_credentials['client_secret'],
            password=self.reddit_credentials['password'],
            user_agent=self.reddit_credentials['user_agent'],
            username=self.reddit_credentials['username']
        )

        if output_folder:
            if os.path.exists(output_folder):
                raise Exception("output path not exists")
            file_submissions = os.path.join(output_folder, file_submissions)
            file_comments = os.path.join(output_folder, file_comments)

        print(reddit.user.me())
        pbar = tqdm()

        cont = True
        params = {}
        if after:
            if not after.startswith('t3_'):
                after += "t3_"+after
            params = {'after' : after}
        limit = 100
        count_retry = 0
        total = 0
        while cont:
            if count_retry > max_retries:
                raise last_exception
            try:
                for submission in reddit.subreddit(subreddit).new(limit=limit, params=params):
                    count_retry = 0
                    params = {"after": submission.fullname}
                    if int(submission.created) < int(start_utc):
                        cont = False
                        break
                    if int(submission.created) > int(end_utc):
                        pbar.set_description(f"Skiping {submission.id} out of range")
                        pbar.update()
                        continue
                    doc = dict()
                    total += 1
                    pbar.set_description(f"Downloading O.C. {submission.id} Total {total}")
                    pbar.update()
                    for field in self.submission_fields:
                        if field == 'author':
                            doc[field] = str(submission.author) if hasattr(submission, 'comments') else None
                        elif field == 'author_id':
                            doc[field] = submission.author_fullname[3:] if hasattr(submission,
                                                                                   'author_fullname') else None
                        elif field == 'subreddit':
                            doc[field] = str(submission.subreddit) if hasattr(submission, 'subreddit') else None
                        else:
                            doc[field] = getattr(submission, field, None)

                    if download_coments:
                        if hasattr(submission, 'comments'):
                            submission.comments.replace_more(limit=None)
                            doc['replies'] = self.__procReplies__(submission.comments, file_comments)
                    self.__append_json_string__(file_submissions, json.dumps(doc))

            except prawcore.exceptions.ServerError as e:
                    # wait for 30 seconds since sending more requests to overloaded server
                    last_exception = e
                    print("Reddit server response error:", e.response.status_code)
                    print("Waiting 30 seconds to retry the request")
                    count_retry += 1
                    time.sleep(30)
                    print("Retrying downlaod submissions . Attempts retry count: ", count_retry)

        print("Generated submissions file " + file_submissions)
        print("Generated comments file " + file_comments)
        print('Download completed. Started at ', start, 'finished at ', dt.datetime.now())
    """