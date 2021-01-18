from .utils import get_vectors, union

import numpy as np
from sklearn.preprocessing import normalize

from flask_login import current_user


class Generator(object):
	""" Base class for Explorator and Consolidator.
	"""
	def __init__(self, embedding_model):
		self.embedding_model = embedding_model

	def __iter__(self):
		return self

	def __next__(self):
		return ValueError("Next method not implemented.")

	def compute_center(self, value_id, Value, Keyword):
		""" Get the value cluster center as the normalized sum of the embeddings of the keywords + value name.
		"""
		# Get value and keywords.
		value    = Value.query.get(value_id)
		keywords = Keyword.query.filter_by(value=value_id)

		value_name    = value.name
		keyword_names = [k.name for k in keywords]

		# Embed all keywords and value key and take the normalized sum as center.
		vectors = get_vectors(union(value_name, keyword_names), self.embedding_model)
		center  = normalize([np.sum(vectors, axis=0)])[0]

		# Update center in database.
		value.center = center.tobytes()

		return value

