# RedditCollector Module Documentation

## Overview
The `RedditCollector` module provides functionality to collect Reddit threads from specified subreddits using the 
Reddit API. It allows users to:
- Search for posts based on date ranges and post IDs.
- Configure Reddit API credentials.
- Download and save collected data (posts and comments) in JSON and CSV formats.

---

## Table of Contents
- [Class: RedditCollector](#class-redditcollector)
  - [Initialization](#initialization)
  - [Collecting Additional Fields Beyond the Defaults](#collecting-additional-fields-beyond-the-defaults-)
  - [Data Collection Process](#data-collection-process-)
    - [Collecting IDs](#step-1-collecting-ids-)
    - [Downloading Posts and Comments](#step-2-downloading-posts-and-comments-)
    - [Restarting the Download](#restarting-the-download-)
    - [Loading Data into a Comid Object](#step-3-loading-data-into-a-comid-object-)
  - [Methods](#methods)
    - [search_ids_by_datetime](#search_ids_by_datetime)
    - [load_ids_file](#load_ids_file)
    - [config_credentials](#config_credentials)
    - [download_by_ids](#download_by_ids)
    - [Private Utility Methods](#private-utility-methods)
- [Usage Example](#usage-example)
- [Dependencies](#dependencies)

---

## Class: `RedditCollector`

### Initialization
The `RedditCollector` class initializes with default fields for submissions and comments.

**Submission fields**

A submission refers to the main topic of a thread, also known as the original post (OP) or original content (OC). 
The table below lists the fields that are collected by default. 


| Attribute | Description |
| --- | --- |
| **id** | Post ID |
| **author** | Post author username |
| **author_id** | Post author ID (substring from author_fullname) |
| **author_flair_text** | Author’s self description |
| **created** |  UTC OC creation datetime |
| **title** | Title of the OC, NULL if no text |
| **selftext** | Markdown formated content for a text of the OC |
| **link_flair_text** | Category that the author/moderator sets for OC, NULL if no text |
| **ups** | Upvotes count |
| **downs** | Downvotes count |
| **upvote_ratio** | OC upvote ratio (percentage of votes that are upvotes) |
| **score** | OC total score (ups minus down) |
| **num_comments** | Number of comments on the submission |
| **num_crossposts** | Number of the OC posts to multiple subreddits |
| **replies** | Array with the ids of all comments to the OC |


**Comments fields**

A comment refers to a post made directly on a submission or in response to another comment. The table below lists the 
fields of a comment that are collected by default.

| Attribute | Description |
| --- | --- |
| **id** | Comment ID |
| **author** | Comment author username |
| **author_id** | Comment author ID |
| **parent_id** | ID of the post to which the comment has been made |
| **body** | Text of the comment |
| **ups** | Upvotes count |
| **downs** | Downvotes count |
| **score** | Comment total score (ups minus down) |
| **author_flair_text** | Category of the comment made by author |
| **controversiality** | Score whether comment is controversial or not |
| **replies** | Array with the ids of all replies to the comment or reply |

To properly initialize the RedditCollector, you need Reddit API access credentials. If you don’t have them yet, 
you can follow the steps in [How to obtain Reddit API credentials](https://www.geeksforgeeks.org/how-to-get-client_id-and-client_secret-for-python-reddit-api-registration/)

```python
from comid.collector import RedditCollector

# Initialize the RedditCollector
collector = RedditCollector()

# Configure Reddit API credentials
collector.config_credentials(
    client_id="your_client_id",
    client_secret="your_client_secret",
    password="your_password",
    username="your_username"
)
```

### Collecting Additional Fields Beyond the Defaults  

The `RedditCollector` class allows customization of the fields collected from both submissions and comments. By default, the `submission_fields` attribute contains a predefined list of fields for original posts. To collect additional fields, simply add the desired field to this list.  

**Example: Adding the `edited` field to submission collection:**  
```python
from comid.collector import RedditCollector

collector = RedditCollector()

# Print default fields for submissions
print(collector.submission_fields)
# Output:
# ['all_awardings', 'author', 'author_id', 'author_flair_text', 'created', 'downs', 'id', 
#  'link_flair_text', 'num_comments', 'num_crossposts', 'permalink', 'score', 'selftext', 
#  'subreddit', 'title', 'total_awards_received', 'ups', 'upvote_ratio']

# Add the 'edited' field to the submission fields list
collector.submission_fields.append('edited')

print(collector.submission_fields)
# Output:
# ['all_awardings', 'author', 'author_id', 'author_flair_text', 'created', 'downs', 'id', 
#  'link_flair_text', 'num_comments', 'num_crossposts', 'permalink', 'score', 'selftext', 
#  'subreddit', 'title', 'total_awards_received', 'ups', 'upvote_ratio', 'edited']
```

Similarly, the `comments_fields` attribute lists the fields collected from comments and replies. You can expand this list by adding any other field that Reddit’s API supports.  

**Example: Adding the `approved_by` field to comment collection:**  
```python
# Print default fields for comments
print(collector.comments_fields)
# Output:
# ['all_awardings', 'author', 'author_id', 'author_flair_text', 'body', 'controversiality',
#  'created', 'depth', 'downs', 'id', 'parent_id', 'permalink', 'score', 'subreddit', 
#  'total_awards_received', 'ups']

# Add the 'approved_by' field to the comment fields list
collector.comments_fields.append('approved_by')

print(collector.comments_fields)
# Output:
# ['all_awardings', 'author', 'author_id', 'author_flair_text', 'body', 'controversiality',
#  'created', 'depth', 'downs', 'id', 'parent_id', 'permalink', 'score', 'subreddit', 
#  'total_awards_received', 'ups', 'approved_by']
```

### Data Collection Process  
Data collection is an iterative process that organizes the content in a specified folder. This process consists of two 
main steps: collecting the IDs of the Original Content (OC) and downloading the associated posts and comments.  

#### Step 1: Collecting IDs  
The process begins by retrieving the IDs of Original Content (OC) that match the search query. These IDs are saved in a 
CSV file, where:  
- **Column 1**: OC ID  
- **Column 2**: Timestamp of the OC's creation date  

The IDs are added iteratively with each search and saved in a CSV file named automatically using the following pattern:  
`{subreddit_name}_ids_{file_creation_timestamp}.csv`  

**Example:** Collecting IDs using `search_ids_by_datetime`:  
```python
from comid.collector import RedditCollector  
import datetime as dt  

start_dt = dt.datetime(2023, 1, 1)  
end_dt = dt.datetime(2023, 1, 2)  
collector = RedditCollector()  

collector.search_ids_by_datetime('digitalnomad', start_dt, end_dt)  
```  

If the IDs were just collected during the same instance, there’s no need to reload them from the CSV file. However, if 
you want to collect posts using IDs from a previously saved CSV file, you can load the file as follows:  

```python
collector.load_ids_file('ids.csv')  
```  

#### Step 2: Downloading Posts and Comments  
Once the IDs have been collected, you can begin downloading the posts. The downloaded content is automatically saved in 
two separate JSON files:  
- **Submissions file**: Contains only the Original Content (OC)  
- **Comments file**: Contains all comments and replies related to the collected posts  

These files are updated during each download iteration to ensure that no data is lost in case of an application 
interruption.  

**Example:** Downloading posts using `download_by_ids`:  
```python
collector.download_by_ids()  
```  

- **OC file**: `submissions_{file_creation_timestamp}.json`  
- **Comments file**: `comments_{file_creation_timestamp}.json`  

In case the download process is interrupted, the remaining IDs are saved in a CSV file named `remaining_ids_{file_creation_timestamp}.csv`.  

#### Restarting the Download  
If the download was interrupted, follow these steps to resume:  

1. **Load the remaining IDs from the `remaining_ids` file:**  
    ```python
    collector.load_ids_file('remaining_ids_{file_creation_timestamp}.csv')  
    ```  

2. **Continue the download process:**  
    ```python
    collector.download_by_ids()  
    ```  

The new OC and comment data will be saved in separate files without overwriting the previously downloaded data.  

#### Step 3: Loading Data into a Comid Object  
After collecting and downloading the data, you can load it into a `comid` object for further processing. This can be 
done by loading the generated JSON files.  

**Example:** Loading JSON files into a `comid` object:  
```python
from comid import Comid  
cm = Comid()  

# Load multiple JSON files into a comid object  
files = ['dataset/submissions.json', 'dataset/comments.json']  
cm.load_json_files(files=files)  
```  

By following this structured process, you ensure a seamless workflow for collecting data.

### Methods

#### `search_ids_by_datetime(subreddit, start_datetime, end_datetime, file_name=None)`
Search for post IDs in a specified subreddit based on a date range and save them to a file.

**Arguments**:
- `subreddit (str)`: The subreddit to collect posts from.  
- `start_datetime (datetime)`: The start date and time for the search.  
- `end_datetime (datetime)`: The end date and time for the search.  
- `file_name (str, optional)`: The name of the file to save the post IDs. Defaults to `None`.  

**Returns**:  
Saves collected post IDs to a CSV file and prints the total number of collected IDs.

---

#### `load_ids_file(file_name, id_col_index=0)`
Load post IDs from a CSV file and store them in the `ids` attribute.

**Arguments**:
- `file_name (str)`: The name of the CSV file containing the post IDs.  
- `id_col_index (int, optional)`: The column index for the post IDs. Defaults to `0`.  

---

#### `config_credentials(client_id, client_secret, password, username, user_agent='comid')`
Configure the Reddit API credentials for authentication.

**Arguments**:
- `client_id (str)`: The Reddit app client ID.  
- `client_secret (str)`: The Reddit app client secret.  
- `password (str)`: The Reddit account password.  
- `username (str)`: The Reddit account username.  
- `user_agent (str, optional)`: The user agent for the API requests. Defaults to `'comid'`.  

---

#### `download_by_ids(download_comments=True, ids=None, output_folder=None, max_retries=50)`
Download submissions and comments by their IDs and save them to JSON files.

**Arguments**:
- `download_comments (bool, optional)`: Whether to download comments. Defaults to `True`.  
- `ids (list, optional)`: A list of submission IDs to download. Defaults to `None`.  
- `output_folder (str, optional)`: The folder to save the downloaded data. Defaults to `None`.  
- `max_retries (int, optional)`: The maximum number of retries for failed downloads. Defaults to `50`.  

**Raises**:  
- `Exception`: If `max_retries` is negative or the output folder does not exist.

**Output**:  
Saves downloaded submissions and comments to JSON files and prints the process summary.

---

#### Private Utility Methods

- `__procReplies__(replies, file_comments)`:  
  Recursively process replies and save them to a comments file. Returns a list of processed reply IDs.

- `__append_new_line__(file_name, text_to_append)`:  
  Append a new line of text to the end of a file.

- `__append_json_string__(file_name, json_text)`:  
  Append a JSON string to a JSON file.

- `__write_remaining_ids(file_name, ids)`:  
  Write remaining IDs to a CSV file.

---

## Usage Example

```python
from datetime import datetime
from comid.collector import RedditCollector

# Initialize the RedditCollector
collector = RedditCollector()

# Configure Reddit API credentials
collector.config_credentials(
    client_id="your_client_id",
    client_secret="your_client_secret",
    password="your_password",
    username="your_username"
)

# Search for post IDs in the 'python' subreddit between two dates
start_date = datetime(2023, 1, 1)
end_date = datetime(2023, 1, 31)
collector.search_ids_by_datetime('python', start_date, end_date)

# Download the posts and comments by IDs
collector.download_by_ids(download_comments=True)
```

---

## Dependencies
The `RedditCollector` module requires the following Python libraries:
- `time`
- `praw`  
- `prawcore`  
- `datetime`  
- `csv`  
- `os`  
- `json`  
- `tqdm`  
- `PullPushApi` (from `comid.pullpush`)  

You can install the dependencies using the following command:
```bash
pip install praw tqdm
```

---

## Notes
- Ensure your Reddit API credentials are correctly configured to avoid authentication errors.
