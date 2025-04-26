# **COMID - Community Identification Module for Reddit Conversations**

**COMID** is a Python toolkit specifically designed for collecting and analyzing Reddit conversations. It offers powerful tools for building corpora, annotating topics, and performing temporal analyses of discussions from subreddit threads.

## **Features**

### What COMID Can Do:
- Collect conversation threads from any specified subreddit.
- Explore and preprocess collected data for detailed analysis.
- Generate a corpus based on the original content (O.C.) of Reddit threads.
- Assist in annotating topics within pre-grouped conversation clusters.
- Perform temporal analysis to track the evolution of topics over time.
- Integrate with [Convokit](https://github.com/CornellNLP/ConvoKit)

### What COMID Does Not Do:
- COMID does **not** perform topic modeling directly. For that, consider using the complementary [hSBM Topic Model](https://github.com/martingerlach/hSBM_Topicmodel).

### Documentation:
Comprehensive documentation is available for each module:
- [Comid](docs/Comid.md)
- [Collector](docs/RedditCollector.md)
- [Explorer](docs/Explorer.md)
- [ConvoBridge](docs/ConvoBridge.md)

## **Quick Start**

### Installation:
To install COMID and configure its dependencies, run the following commands:
``` bash
pip install comid
python -m spacy download en_core_web_sm
```

### Setting Up Reddit Credentials:
To use COMID, initialize your Reddit API credentials. If you don’t already have these credentials, you can follow this [guide](https://www.geeksforgeeks.org/how-to-get-client_id-and-client_secret-for-python-reddit-api-registration/).
``` python
from comid.collector import RedditCollector
import datetime as dt

collector = RedditCollector()

# Configure Reddit API credentials
collector.config_credentials(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    password="YOUR_PASSWORD",
    username="YOUR_USERNAME"
)
```

## **Collecting Data**

### Specify Subreddit and Date Range:
Define the subreddit and the range of dates to collect conversation thread IDs:
``` python
subreddit = 'digitalnomad'
start_dt = dt.datetime(2022, 1, 1)
end_dt = dt.datetime(2022, 1, 2)

# Collect thread IDs for the specified subreddit and date range
collector.search_ids_by_datetime(subreddit, start_dt, end_dt)
```

### Download Submissions and Comments:
Once the IDs are collected, download all data, including original content, comments, and replies:
``` python
collector.download_by_ids()
```

## **Exploring Data and Creating a Corpus**
### Load JSON Data:
After downloading the data, load it from JSON files into COMID.
``` python
from comid import Comid

cm = Comid()
files = ['dataset/submissions.json', 'dataset/comments.json']
cm.load_json_files(files=files)
```

### Explore Collected Data:
Perform exploratory data analysis to understand the dataset:
``` python
from comid.explorer import Explorer

# Initialize the Explorer with the loaded posts
explorer = Explorer(cm.posts)

# Display a summary of the dataset
explorer.data_summary()

# Calculate interval-based thread activity (e.g., by month)
explorer.thread_interval_activity('m')

# Export statistical data to files
explorer.export_data()
```

### Generate the Corpus:
Extract only the main submissions to create a corpus. This step may take a few minutes for large datasets:
``` python
cm.generate_corpus()
print("Corpus size:", len(cm.corpus))
```

### Reduce the Corpus:
For efficient topic modeling, it is recommended to keep the corpus size under **6,000 documents**. Filter out posts with fewer than a specified number of interactions (e.g., 10 comments or replies):
``` python
cm.reduce_corpus(target_size=6000, min_num_interactions=10)
print("Corpus size:", len(cm.corpus))
print("Reduced corpus size:", len(cm.corpus_reduced))
```

## **Saving and Loading Data**

### Save the Corpus:
Save the reduced corpus as a JSON file for compatibility with hSBM Topic Modeling:
``` python
cm.save_corpus(reduced=True)
```
For details on working with hSBM, refer to the [hSBM Documentation](docs/SBM.md).

### Save and Load COMID Instances:
Save the current state of COMID for later use:
``` python
# Save the instance
cm.save("comid_saved_file.pickle")

# Reload the saved COMID instance
from comid import Comid

cm = Comid.load("comid_saved_file.pickle")
```

## **Working with Clusters and Topics**

### Load Topic Clusters:
After performing topic modeling with hSBM, load the generated clusters file for analysis:
``` python
cluster_file = 'path_to_file/topsbm_level_1_clusters.csv'
cm.load_clusters_file(cluster_file)
cm.df_clusters.head()
```

### Analyze Clusters:
Perform various operations on the topic clusters, such as viewing random samples or generating summaries:

#### Display Cluster Samples:
View random samples from any cluster to explore associated documents:
``` python
cm.print_cluster_samples('Cluster 1', 3)
```

#### Retrieve Flattened Conversation Text:
Flatten the conversational data for a specific document ID:
``` python
doc_id = 'rtsodc'
text = cm.retrieve_conversation(doc_id)
print(text)
```

#### Save Cluster Summary:
Create and save a summary of clusters, including cluster statistics and a topic label column for annotation:
``` python
cm.save_clusters_summary()
```


## **Building and Analyzing Topics**

### Build the Topics DataFrame:
Once clusters have been annotated with topic labels, build a topics DataFrame:
``` python
cm.build_topics("clusters_summary.csv")
cm.df_topics.head()
```
Alternatively, generate the topics DataFrame based on clusters containing a minimum percentage of documents (e.g., 7%):
``` python
cm.build_topics(min_percent=7)
```

### Temporal Topic Analysis:
Group topics by time intervals, such as days, weeks, months, or years:
``` python
cm.group_by_period(period_type="m")
cm.df_periods.head()
```
Temporal analysis helps track the progression and evolution of topics over time.
