from gensim.models import KeyedVectors
import numpy as np
from sentence_transformers import SentenceTransformer


# Colorblind-friendly color map from annotation action to bar color.
color_map = {
		'add_value'       : '#31a354',  # Dark green    # add value
		'add_keyword'     : '#a1d99b',  # Light green   # add keyword
		'add_many'        : '#74c476',  # Green         # add values and keywords
		'remove_value'    : '#e6550d',  # Dark red      # remove value
		'remove_keyword'  : '#fdae6b',  # Light red     # remove keyword
		'remove_many'     : '#fd8d3c',  # Red           # remove values and keywords
		'multi_actions'   : '#9e9ac8',  # Purple        # combination of actions above
		'already_present' : '#3182bd',  # Dark blue     # skip motivation (value already present)
		'generic_skip'    : '#6baed6',  # Blue          # skip motivation (no value or incomprehensible)
		'similarity'      : '#969696',  # Gray          # Similar motivation was shown
		'no_action'       : '#969696',  # Gray          # no annotation action (should never be invoked)
}


# Colorblind-friendly color map from consolidation action to bar color.
csd_color_map = {
		'add_value'       : '#31a354',  # Dark green    # add value
		'add_keyword'     : '#a1d99b',  # Light green   # add keyword
		'add_many'        : '#74c476',  # Green         # add values and keywords
		'remove_value'    : '#e6550d',  # Dark red      # remove value
		'remove_keyword'  : '#fdae6b',  # Light red     # remove keyword
		'remove_many'     : '#fd8d3c',  # Red           # remove values and keywords
		'merge'           : '#756bb1',  # Dark purple   # Merge of shown values
		'multi_actions'   : '#9e9ac8',  # Purple        # combination of actions above
		'skip'            : '#6baed6',  # Blue          # skip couple
}


def union(foo, bar):
	""" Return union of two lists. Wrapper around set.union() method.
	"""
	if not isinstance(foo, list):
		foo = [foo]
	if not isinstance(bar, list):
		bar = [bar]

	return list(set().union(foo, bar))


def get_embedding_models(lang='en'):
	""" Get lexicon expansion embedding model (counterfitted model,
		available only in English) and S-BERT embedding model.
	"""
	# Load counterfitted model.
	cf_model = KeyedVectors.load_word2vec_format('./static/models/counter-fitted-vectors.bin', binary=True)

	# Load Sentence-BERT model.
	if lang == 'nl':
		embedding_model = SentenceTransformer('distiluse-base-multilingual-cased')
	elif lang == 'en':
		embedding_model = SentenceTransformer('bert-base-nli-mean-tokens')
	else:
		raise ValueError("Language not supported. Please choose 'en' or 'nl'.")

	return cf_model, embedding_model


def get_vectors(phrases, model):
	""" Embed phrases with SentenceTransformer model.
	"""
	return np.array(model.encode(phrases), dtype=np.float)

