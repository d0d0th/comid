# COMID - Community identification module for Reddit conversations

COMID is a package of tools for analyzing conversations on Reddit

### What does COMID?

- Collects submissions from a subreddit
- Generates a corpus based on the O.C. (original content) of the submissions.
- Assists in the annotation of topics in pre-grouped conversation clusters.
- Conducts temporal analysis of topics.

### What does Comid not do?

- Comid does not conduct topic modeling. For topic modeling, we recommend using the SBM [https://github.com/martingerlach/hSBM_Topicmodel](https://github.com/martingerlach/hSBM_Topicmodel).

# Quick Start

Install Comid and download the en_core_web_sm model

```bash
pip install comid
python -m spacy download en_core_web_sm
```

Import RedditScrapper submodule, creates a RedditScraper instance and configure the reddit credentials. 

If you don’t have the credentials, you can follow the instructions here: 

[How to get client_id and client_secret for Python Reddit API registration ? - GeeksforGeeks](https://www.geeksforgeeks.org/how-to-get-client_id-and-client_secret-for-python-reddit-api-registration/)

```python
from comid.scraper import RedditScraper
import datetime as dt

rscrap = RedditScraper()

#setup reddit credentials
rscrap.config_credentials(
    client_id= "YOUR_CLIENT_ID",
    client_secret= "YOUR_CLIENT_SECRET",
    password= "YOUR_PASSWORD",
    username= "YOUR_USERNAME"
)
```

Inform the subreddit and date range and download the O.C. ids.

```python
subreddit = 'digitalnomad' # the subreddit
start_dt = dt.datetime(2022,1,1) # the initial date
end_dt = dt.datetime(2022,1,2) #the final date

# downlaod the O.C ids of given subreddit and date range
rscrap.search_ids_by_datetime(subreddit,start_dt,end_dt)
```

Download all submissions of collected ids, including O.C, comments and replies

```python
rscrap.donwload_by_ids()
```

Import Comid and load the json files of files of Reddit submissions. 

```python
from comid import Comid
cm = Comid()
# Load all json files as a list. You can use full or relative path for every file
files = ['dataset/submissions.json','dataset/comments.json']
cm.load_json_files(files=files)
```

Generate the corpus of submission posts. The corpus includes only the main submission, not will include the comments and replies. This step can expends few minutes if has a large number of posts.

```python
cm.generate_corpus()
```

Once generated, The corpus can be accessed in the atribute `corpus`. Explore the corpus and check the corpus size.

```python
print("corpus size: ",len(cm.corpus))
```

For a reasonable runtime topic modelling using SBM, it is recommended that the corpus does not exceed the approximate size of 6000 documents.  If the corpus is too large, perform the next step to shrink the corpus.

```python
# reduce the corpus by optimizing the number of tokens and pinning documents that have
# at last 10 interactions (comments or replies)
cm.reduce_corpus(target_size=6000,optimize_num_interactions=False,min_num_interactions=10)
#print the full corpus length vs reduced corpus length
print("corpus: ",len(cm.corpus),"corpus_reduced: ",len(cm.corpus_reduced))
```

Save the corpus as a json to used in HSMB

```python
# gerating json of reduced corpus
cm.save_corpus(reduced=True)
```

Save the current Comid instance in a pickle file to be loaded anytime.

```python
cm.save()
```

Use the json file of corpus in a topic modelling. For Comid, it is recommended the use of SBMTopic Model. Here is a guide how to use the corpus in SBM [SBM Topic Model](SBM.md). Once the topic modelling is finished, the previous Comid state can be loaded.

```python
from comid import Comid
# replace the comid_file_name with the name of the file to be loaded
comid_file_name = "comid_saved_file.pickle"
cm = Comid.load(comid_file_name)
```

Load the CSV clusters file generated in topic modelling

```python
# replace the cluster_file with the name of the file to be loaded
cluster_file = 'path_to_file/topsbm_level_1_clusters.csv'
cm.load_clusters_file(cluster_file )
# show clusters dataframe
cm.df_clusters.head()
```

Print random samples from any Cluster executing the method `print_cluster_samples` 

```python
# Printing 3 random samples from 'Cluster 1'
cm.print_cluster_samples('Cluster 1',3)
```

Also, it is possible to retrieve a conversation flatten text by a document id

```python
# replace the doc_id with the id of document to retrieve
doc_id = 'rtsodc'
text = c.retrieve_conversation(doc_id)
print(text)
```

Save a CSV summary of clusters. The summary file contains four columns: Cluster (cluster id), Num Docs (number of documents in cluster), Percent (percentual of documents in the cluster from all documents) and Topic (To annotate the topic label).

```python
cm.save_clusters_summary()
```

Use the saved file in previous step to annotate the topics label in the `Topic`  column. 

 Build the topics data frame from Topics annotated in cluster summary CSV. Clusters not annotated will not be included in the data frame.

```python
cm.build_topics("clusters_summary.csv")
cm.df_topics.head()
```

Alternatively, it is possible to build the topics data frame without annotate the topic labels. In this case, it this case the method will consider a minimum value for the percentual of documents to include the cluster in the topic data frame. 

```python
# build the df_topics just for the clusters with a minimal of 7% of documents. 
# if omitted the parameter min_percent, it will consider 10% 
cm.build_topics(min_percent=7)
```

Explore the topics grouping them by periods

```python
# Group topics by months. 
# parameter period_type can be 'd' for days, 'w' for weeks, 'm' for months and
# 'y' for years
cm.group_by_period(period_type="m")
cm.df_periods
```