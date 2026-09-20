from convokit import Utterance, Speaker, Corpus, TextProcessor
from tqdm import tqdm
from comid import Comid
from comid.explorer import Explorer

"""
This module integrates Comid's Reddit data with Convokit's conversational structure to create and process corpora.

Classes:
    - ConvoCorpus: Converts Reddit posts from the Comid dataset into Convokit-compatible corpus structure.
    - ConvoTextParser: Text processing class for tokenizing and filtering utterances in the corpus.

Functions:
    - filter_utt: Filters utterances based on inclusion parameters (OC or comments).
    - process_text: Tokenizes and processes text using Comid's tokenizer.

Dependencies:
    - convokit: Utterance, Speaker, Corpus, TextProcessor
    - tqdm: For progress visualization
    - comid: Comid dataset and Explorer utility
"""

class ConvoCorpus(Corpus):
    """
    A Convokit-compatible corpus builder that converts a Comid dataset into structured conversations.

    Attributes:
        comid (Comid): The Comid dataset containing Reddit posts.
        speaker_meta_keys (list): Keys from the Comid dataset to include in Speaker metadata.
        utt_meta_keys (list): Keys from the Comid dataset to include in Utterance metadata.
    """
    comid: Comid

    def __init__(self, comid: Comid,
                 speaker_meta_keys=['author', 'author_flair_text'],
                 utt_meta_keys=['subreddit', 'depth']):
        """
        Initialize the ConvoCorpus class.

        Parameters:
            comid (Comid): The Comid dataset containing Reddit posts.
            speaker_meta_keys (list): Metadata fields to include for speakers (default: ['author', 'author_flair_text']).
            utt_meta_keys (list): Metadata fields to include for utterances (default: ['subreddit', 'depth']).

        Returns:
            None
        """

        self.comid = comid
        utterances = []
        speakers = {}
        explorer = Explorer(comid.posts)

        if 'subreddit' not in utt_meta_keys:
            utt_meta_keys.append('subreddit')
        if 'depth' not in utt_meta_keys:
            utt_meta_keys.append('depth')

        for oc, replies in tqdm(explorer.thread_replies.items(), "Creating convokit data"):
            if comid.posts[oc]['author_id'] not in speakers:
                speakers[comid.posts[oc]['author_id']] = Speaker(id=comid.posts[oc]['author_id'], meta={
                    key: comid.posts[oc][key] if key in comid.posts[oc] else None for key in speaker_meta_keys
                })
            utterances.append(Utterance(
                id=oc,
                speaker=speakers[comid.posts[oc]['author_id']],
                conversation_id=oc,
                timestamp=comid.posts[oc]['created'],
                text=comid.posts[oc]['full_text'],
                meta={
                    key: comid.posts[oc][key] if key in comid.posts[oc] else None for key in utt_meta_keys
                }
            ))
            for reply in replies:
                if comid.posts[reply]['author_id'] not in speakers:
                    speakers[comid.posts[reply]['author_id']] = Speaker(id=comid.posts[reply]['author_id'], meta={
                        key: comid.posts[reply][key] if key in comid.posts[reply] else None for key in speaker_meta_keys
                    })
                utterances.append(Utterance(
                    id=reply,
                    speaker=speakers[comid.posts[reply]['author_id']],
                    conversation_id=oc,
                    reply_to=comid.posts[reply]['parent_id'],
                    timestamp=comid.posts[reply]['created'],
                    text=comid.posts[reply]['full_text'],
                    meta={
                        key: comid.posts[reply][key] if key in comid.posts[reply] else None for key in utt_meta_keys
                    }
                ))
        super().__init__(utterances=utterances)

class ConvoTextParser(TextProcessor):

    """
    A text processor for Convokit corpus, designed for tokenizing and filtering utterances.

    Attributes:
        comid (Comid): The Comid dataset for text processing.
        model (str): The language model used for text processing (default: "en_core_web_sm").
        input_field (str): Input field for processing (default: None).
        output_field (str): Output field to store processed data (default: "parsed").
        tags (list): POS tags to retain in the processed text (default: ["NOUN", "VERB", "ADJ", "PROPN"]).
        min_size (int): Minimum token size for inclusion (default: 3).
        include_oc (bool): Whether to include Original Content (OC) in the corpus (default: True).
        include_comments (bool): Whether to include comments in the corpus (default: False).
        verbosity (int): Frequency of logging progress (default: 1000).
    """
    convoCorpus: ConvoCorpus

    def __init__(
            self,
            comid: Comid,
            model="en_core_web_sm",
            input_field=None,
            output_field="parsed",
            tags = ["NOUN", "VERB", "ADJ", "PROPN"],
            min_size=3,
            include_oc=True,
            include_comments=False,
            verbosity=1000):
        """
        Initialize the ConvoTextParser class.

        Parameters:
            comid (Comid): The Comid dataset for text processing.
            model (str): Language model for text processing (default: "en_core_web_sm").
            input_field (str): Input field for processing (default: None).
            output_field (str): Output field to store processed data (default: "parsed").
            tags (list): POS tags to retain (default: ["NOUN", "VERB", "ADJ", "PROPN"]).
            min_size (int): Minimum token size for inclusion (default: 3).
            include_oc (bool): Include Original Content in processing (default: True).
            include_comments (bool): Include comments in processing (default: False).
            verbosity (int): Progress logging frequency (default: 1000).

        Returns:
            None
        """

        self.comid = comid
        self.tags = tags
        self.min_size = min_size
        self.include_oc = include_oc
        self.include_comments = include_comments

        self.comid.spacy_load(model)
        input_filter = lambda utt: filter_utt(utt,include_oc,include_comments)
        TextProcessor.__init__(
            self,
            proc_fn=self._process_text_wrapper,
            input_field=input_field,
            output_field=output_field,
            input_filter=input_filter,
            verbosity=verbosity
        )

    def _process_text_wrapper(self, text, aux_input={}):
        """
        Process the text using Comid's tokenizer.

        Parameters:
            text (str): The text to process.
            aux_input (dict): Auxiliary inputs (default: empty dict).

        Returns:
            list: Processed tokens.
        """
        return process_text(
            text,
            aux_input.get("comid", self.comid),
            aux_input.get("tags", self.tags),
            aux_input.get("min_size", self.min_size),
        )

def filter_utt(utt,include_oc,include_comments):
    """
    Filter utterances based on whether they should include Original Content (OC) or comments.

    Parameters:
        utt (Utterance): The utterance to filter.
        include_oc (bool): Include OCs in the corpus.
        include_comments (bool): Include comments in the corpus.

    Returns:
        bool: True if the utterance passes the filter, False otherwise.
    """
    if utt.meta['depth'] is None:
        if include_oc:
            return True
    elif include_comments and utt.meta['depth'] == 0:
        return True
    return False

def process_text(text,comid,tags,min_size):
    """
    Tokenize and process text using Comid's tokenizer.

    Parameters:
        text (str): The text to process.
        comid (Comid): The Comid instance handling text processing.
        tags (list): POS tags to retain.
        min_size (int): Minimum token size for inclusion.

    Returns:
        list: Processed tokens.
    """
    return comid.text_tokenizer(text, tags=tags, min_size=min_size)