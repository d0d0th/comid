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
    A class to collect Reddit threads and comments from specified subreddits.

    This class provides functionalities to search, collect, and store Reddit
    posts and comments based on given date ranges and post IDs. It uses the Reddit
    API for data collection and offers methods to download and save the collected
    data in JSON and CSV formats.
    """

    def __init__(self):
        """Initialize the RedditCollector with default submission and comment fields, and Reddit API credentials."""
        self.ids = list()
        self.submission_fields = ['author', 'author_id', 'author_flair_text', 'created', 'downs',
                                  'id', 'link_flair_text', 'num_comments', 'num_crossposts', 'permalink', 'score',
                                  'selftext', 'subreddit', 'title', 'ups', 'upvote_ratio']
        self.comments_fields = ['author', 'author_id', 'author_flair_text', 'body',
                                'controversiality', 'created', 'depth', 'downs', 'id', 'parent_id', 'permalink',
                                'score', 'subreddit', 'ups']
        self.reddit_credentials = {
            'client_id': 'Put your reddit api client id here',
            'client_secret': 'Put your reddit api client secret here',
            'password': 'Put your reddit api password here',
            'user_agent': 'comid RedditCollector',
            'username': 'Put your reddit api username here'
        }

    def search_ids_by_datetime(self, subreddit, start_datetime, end_datetime, file_name=None):
        """
        Search for post IDs in the PullPush repository by date range and save them to a file.

        Args:
            subreddit (str): The subreddit to collect posts from.
            start_datetime (datetime): The start date and time for the search.
            end_datetime (datetime): The end date and time for the search.
            file_name (str, optional): The name of the file to save the post IDs. Defaults to None.
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
        Load post IDs from a CSV file.

        Args:
            file_name (str): The name of the CSV file containing the post IDs.
            id_col_index (int, optional): The column index for the post IDs. Defaults to 0.
        """
        with open(file_name) as csv_file:
            self.ids = list()
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                self.ids.append(row[id_col_index])

    def config_credentials(self, client_id, client_secret, password, username, user_agent='comid'):
        """
        Configure Reddit API authentication credentials.

        Args:
            client_id (str): The Reddit app client ID.
            client_secret (str): The Reddit app client secret.
            password (str): The Reddit account password.
            username (str): The Reddit account username.
            user_agent (str, optional): The user agent for the API requests. Defaults to 'comid'.
        """
        self.reddit_credentials['client_id'] = client_id
        self.reddit_credentials['client_secret'] = client_secret
        self.reddit_credentials['password'] = password
        self.reddit_credentials['user_agent'] = user_agent
        self.reddit_credentials['username'] = username

    def download_by_ids(self, download_comments=True, ids=None, output_folder=None, max_retries=50):
        """
        Download submissions and comments by their IDs and save them to files.

        Args:
            download_comments (bool, optional): Whether to download comments and replies. Defaults to True.
            ids (list, optional): A list of submission IDs to download. Defaults to None.
            output_folder (str, optional): The folder to save the downloaded data. Defaults to None.
            max_retries (int, optional): The maximum number of retries for failed downloads. Defaults to 50.

        Raises:
            Exception: If `max_retries` is negative or the output folder does not exist.
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

                    if download_comments:
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
                except prawcore.exceptions.TooManyRequests as e:
                    # wait for 1 hour since sending more requests to overloaded server
                    last_exception = e
                    print("Reddit server response 429 - Too Many Requests")
                    print("Waiting 1 hour to retry the request")
                    count_retry += 1
                    for i in range(3660, 0, -1):
                        print(f"{i} seconds", end="\r", flush=True)
                        time.sleep(1)

                    print("Retrying submission ", doc_id, "attempts retry count: ", count_retry)

        print("saved submissions file "+file_submissions)
        print("saved comments file " + file_comments)
        print('Download completed. Started at ', start,'finished at ', dt.datetime.now())
        os.remove(file_remaining_ids)

    def __procReplies__(self, replies, file_comments):
        """
        Recursively process replies and save them to a comments file.

        Args:
            replies (praw.models.CommentForest): A collection of replies to process.
            file_comments (str): The name of the file to save the comments.

        Returns:
            list: A list of processed reply IDs.
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

    @staticmethod
    def __append_new_line__(file_name, text_to_append):
        """
        Append a new line of text to the end of a file.

        Args:
            file_name (str): The name of the file to append to.
            text_to_append (str): The text to append as a new line.
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
        Append a JSON string to a JSON file.

        Args:
            file_name (str): The name of the JSON file.
            json_text (str): The JSON string to append.
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
        """
        Write remaining IDs to a CSV file.

        Args:
            file_name (str): The name of the CSV file to write the IDs to.
            ids (list[str]): The list of IDs to be written to the file.
        """
        with open(file_name, "w") as outfile:
            ids_2d = [[id] for id in ids]
            csv_writer = csv.writer(outfile)
            csv_writer.writerows(ids_2d)
