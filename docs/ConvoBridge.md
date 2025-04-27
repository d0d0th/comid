# Documentation: Comid to Convokit Integration Module

## Overview
This module bridges the Reddit dataset from **Comid** with Convokit’s conversational data structures for advanced linguistic analysis and conversational modeling. It allows users to convert Reddit posts into a structured corpus, tokenize utterances, and process them based on specified linguistic features.

## Classes

### `ConvoCorpus`
Transforms a Comid dataset of Reddit posts into a Convokit-compatible corpus, structuring conversations, speakers, and utterances.

#### Attributes:
- **`comid`**: Instance of the Comid dataset containing Reddit posts.
- **`speaker_meta_keys`**: A list of keys to include in speaker metadata (default: `['author', 'author_flair_text']`).
- **`utt_meta_keys`**: A list of keys to include in utterance metadata (default: `['subreddit', 'depth']`).

#### Methods:
- **`__init__(comid: Comid, speaker_meta_keys: list, utt_meta_keys: list)`**
  Initializes the class and processes the Comid dataset into a Convokit-compatible corpus structure.

  **Parameters:**
  - `comid`: Comid instance containing Reddit posts.
  - `speaker_meta_keys`: List of metadata fields to include for speakers.
  - `utt_meta_keys`: List of metadata fields to include for utterances.

---

### `ConvoTextParser`
Processes text in a Convokit corpus, applying tokenization, filtering, and optional linguistic analysis.

#### Attributes:
- **`comid`**: Instance of the Comid dataset.
- **`model`**: NLP language model used for tokenization (default: `"en_core_web_sm"`).
- **`input_field`**: Field in utterances where the text input is located (default: `None`).
- **`output_field`**: Field where processed tokens are stored (default: `"parsed"`).
- **`tags`**: POS tags to retain during tokenization (default: `["NOUN", "VERB", "ADJ", "PROPN"]`).
- **`min_size`**: Minimum token size for inclusion in processed output (default: `3`).
- **`include_oc`**: Whether to include Original Content in processing (default: `True`).
- **`include_comments`**: Whether to include comments in processing (default: `False`).
- **`verbosity`**: Frequency of logging progress (default: `1000`).

#### Methods:
- **`__init__(comid: Comid, model: str, input_field: str, output_field: str, tags: list, min_size: int, include_oc: bool, include_comments: bool, verbosity: int)`**
  Initializes the text processor for linguistic tokenization and filtering.

  **Parameters:**
  - `comid`: Instance of the Comid dataset.
  - `model`: NLP language model for processing.
  - `input_field`: Input field for processing text.
  - `output_field`: Field to store processed tokens.
  - `tags`: List of POS tags to retain during processing.
  - `min_size`: Minimum size of tokens for inclusion.
  - `include_oc`: Whether to include Original Content.
  - `include_comments`: Whether to include comments.
  - `verbosity`: Progress logging frequency.

- **`_process_text_wrapper(self, text, aux_input={})`**
  Wraps the processing function and applies tokenization and filtering.

  **Parameters:**
  - `text`: The input text to process.
  - `aux_input`: Auxiliary inputs for processing.

  **Returns:**
  - List of processed tokens.

---

## Functions

### `filter_utt(utt, include_oc: bool, include_comments: bool)`
Filters utterances based on whether they should include Original Content (OC) or top-level comments.

#### Parameters:
- **`utt`**: The utterance to filter.
- **`include_oc`**: If `True`, includes Original Content in the corpus.
- **`include_comments`**: If `True`, includes comments in the corpus.

#### Returns:
- **`bool`**: `True` if the utterance passes the filter; otherwise, `False`.

---

### `process_text(text: str, comid: Comid, tags: list, min_size: int)`
Tokenizes and processes text using Comid’s text tokenizer.

#### Parameters:
- **`text`**: The input text to process.
- **`comid`**: Instance of the Comid dataset.
- **`tags`**: POS tags to retain during processing.
- **`min_size`**: Minimum size of tokens for inclusion.

#### Returns:
- **`list`**: List of processed tokens.

---

## Dependencies
This module requires the following:
- **Convokit**: For corpus and text processing (`Utterance`, `Speaker`, `Corpus`, `TextProcessor`).
- **Comid**: For managing Reddit datasets.
- **tqdm**: For progress visualization during processing.

---

## Example Usage

### Create a Convokit Corpus:
```python
from comid import Comid
from comid.convobridge import ConvoCorpus

# Load Reddit data using Comid
comid = Comid()
comid.load_json_files(files=['data.json'])

# Create a Convokit-compatible corpus
convo_corpus = ConvoCorpus(comid=comid)
```

### Process Text:
```python
from comid.convobridge import ConvoTextParser

# Initialize text parser
convoTextParser = ConvoTextParser(
    comid=comid,
    output_field="parsed",
    include_oc=True,
    include_comments=True
)

# Process utterances in corpus
convo_corpus = convoTextParser.transform(convoTextParser)
```
### Verify the parsed metadata
Verify if the `parsed` metadata contains the expected processed information. A random utterance is selected using a try-except block to ensure that only utterances with the `words` metadata (top-level comments) are sampled.
```python
fail = True
while fail:
    try:
        utt = convo_corpus.random_utterance()
        utt.meta['parsed']
        fail = False
    except:
        fail = True
print(f"**id** {utt.id}\n**community: {utt.meta['subreddit']}\n**text: {utt.text}\n**parsed: {utt.meta['parsed']}")
```
---
