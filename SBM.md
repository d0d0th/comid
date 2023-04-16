# SBM Topic Model

This project uses the Graph-tool to generate the topics using Stochastic Blocking Model. Installations instructions for Graph-tool can be found here: [https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions](https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions)

Clone the hSBM_TopicModel project from official Github repository 

[GitHub - martingerlach/hSBM_Topicmodel: Using stochastic block models for topic modeling](https://github.com/martingerlach/hSBM_Topicmodel)

```bash
git clone https://github.com/martingerlach/hSBM_Topicmodel.git
```

Copy the file `[sbmtm.py](http://sbmtm.py)` to your python project. Creates a new python ( or Jupyter Notebook). Import all required modules

```python
import json
import statistics
import pickle
import os
from sbmtm import sbmtm
import graph_tool.all as gt
from datetime import datetime

start_time = datetime.now()
```

Load the corpus file 

```python
#replace the corpus_json_file with the name of the file to be loaded
corpus_json_file = 'comid_corpus.json'
with open(corpus_json_file , 'r') as data_file:
    json_data = data_file.read()

data = json.loads(json_data)
documents = list(data.keys())
texts = list(data.values())

#print some basic stats of corpus
print( "number of documents:",len(documents))
sizes = [len(el) for el in texts]
av = round(sum(sizes) / len(sizes))
print("mean of tokens size per doc:",round(statistics.mean(sizes)))
print("median of tokens size per doc:",statistics.median(sizes))
```

Generate the Topic Model

```python
## we create an instance of the sbmtm-class
model = sbmtm()

## we have to create the word-document network from the corpus
model.make_graph(texts,documents=documents)

## we can also skip the previous step by saving/loading a graph
# model.save_graph(filename = 'graph.xml.gz')
# model.load_graph(filename = 'graph.xml.gz')

seed = 32
## fit the model default seed 32
gt.seed_rng(seed) ## seed for graph-tool's random number generator --> same results

model.fit(n_init = 5)

#saving model to load again if needed
model.save_graph(filename = 'graph.xml.gz')
with open('model.pickle', 'wb') as handle:
    pickle.dump(model, handle, protocol=pickle.HIGHEST_PROTOCOL)

#paths to save the cluster file

```

Generate the clusters files

```python
today = datetime.today().strftime('%Y%m%d')

#### uncomment the following code block to save the level 0
"""
print("saving level 0")
path_zero = 'SBM_topics_'+today+'/level_zero/'
if not os.path.exists(path_zero):
  os.makedirs(path_zero)
model.clusters(l=0,n=9999)
model.print_topics(l=0,format='csv', path_save=path_one)
"""
#gerating the clusters of level 1
print("saving level 1")
path_one = 'SBM_topics_'+today+'/level_one/'
if not os.path.exists(path_one):
  os.makedirs(path_one)
model.clusters(l=1,n=9999)
model.print_topics(l=1,format='csv', path_save=path_one)
end_time = datetime.now()
print('Total Duration: {}'.format(end_time - start_time))
```

Use the generated file topsbm_level_1_clusters.csv in Comid