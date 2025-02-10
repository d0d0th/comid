# SBM Topic Model
This project uses the [Graph-tool](https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions) library to generate topics using the Stochastic Block Model (SBM). The process involves creating a word-document network, fitting the SBM model, and extracting clusters of topics from the data.

## Requirements
Ensure Graph-tool is installed in your environment. Follow the installation instructions provided here: [Graph-tool Installation Instructions](https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions).

## Quick Start Guide
### 1. Clone the hSBM_TopicModel Project

To begin, clone the project from its official GitHub repository:
[GitHub - martingerlach/hSBM_Topicmodel](https://github.com/martingerlach/hSBM_Topicmodel)

Run the following command:
``` bash
git clone https://github.com/martingerlach/hSBM_Topicmodel.git
```

Copy the file `sbmtm.py` from the cloned repository into your Python project.

Create a new Python file or Jupyter Notebook, and import the required modules:
``` python
import json
import statistics
import pickle
import os
from sbmtm import sbmtm
import graph_tool.all as gt
from datetime import datetime

start_time = datetime.now()
```

### 2. Load the Corpus File
Load the corpus file (your textual data) into memory. Replace `corpus_json_file` with the name of your JSON file containing the data.

``` python
# Replace with the name of your JSON corpus file
corpus_json_file = 'comid_corpus.json'

# Load the JSON file
with open(corpus_json_file, 'r') as data_file:
    json_data = data_file.read()

data = json.loads(json_data)
documents = list(data.keys())
texts = list(data.values())

# Print some basic statistics about the corpus
print("Number of documents:", len(documents))
sizes = [len(el) for el in texts]
print("Mean size of tokens per document:", round(statistics.mean(sizes)))
print("Median size of tokens per document:", statistics.median(sizes))
```

### 3. Generate the Topic Model

Next, generate the topic model using the SBM approach. This step consists of creating a word-document graph from your data and fitting the model.
``` python
# Create an instance of the sbmtm class
model = sbmtm()

# Create the word-document network from the corpus
model.make_graph(texts, documents=documents)

# Optional: Save or load the graph for faster model reuse
# model.save_graph(filename='graph.xml.gz')
# model.load_graph(filename='graph.xml.gz')

# Fit the model with a default seed for reproducibility
seed = 32
gt.seed_rng(seed)  # Seed for Graph-tool's random number generator
model.fit(n_init=5)

# Save the graph and model for future use
model.save_graph(filename='graph.xml.gz')
with open('model.pickle', 'wb') as handle:
    pickle.dump(model, handle, protocol=pickle.HIGHEST_PROTOCOL)
```

### 4. Generate Topic Clusters

Finally, generate topic clusters from the fitted model. These clusters represent the topics identified in your dataset, organized hierarchically. The cluster information can be exported to CSV files for downstream analysis.
``` python
from datetime import datetime

# Generate a unique path based on the current date
today = datetime.today().strftime('%Y%m%d')

# Uncomment this block to save clusters for level 0
"""
print("Saving level 0 clusters...")
path_zero = 'SBM_topics_' + today + '/level_zero/'
if not os.path.exists(path_zero):
    os.makedirs(path_zero)
model.clusters(l=0, n=9999)
model.print_topics(l=0, format='csv', path_save=path_zero)
"""

# Generate and save clusters for level 1
print("Saving level 1 clusters...")
path_one = 'SBM_topics_' + today + '/level_one/'
if not os.path.exists(path_one):
    os.makedirs(path_one)
model.clusters(l=1, n=9999)
model.print_topics(l=1, format='csv', path_save=path_one)

end_time = datetime.now()
print("Total Duration:", end_time - start_time)
```

### 5. Use the Generated Cluster File in CoMID
After generating clusters, you will find a file named `topsbm_level_1_clusters.csv` in the output folder (e.g., `SBM_topics_<date>/level_one/`). You can use this file in CoMID for further processing and exploration.

## Additional Notes
- **Performance Tip**: For large corpora, saving/loading the graph and model can save time on subsequent runs.
- **Reproducibility**: Setting a random seed ensures that results are consistent for multiple runs.
- **Command Summary**: Make use of the steps above to efficiently generate topics and clusters from your data.

