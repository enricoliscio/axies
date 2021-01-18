from .utils import color_map
from .generator import Generator

from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
import numpy as np
import random
from scipy.spatial.distance import cdist

from flask_login import current_user


default_config = {
		'corona-vectors' : './static/models/corona_vectors.npy',
		'swf-vectors'    : './static/models/swf_vectors.npy',
		'corona-context' : 'PVE: COVID Exit',
		'swf-context'    : 'PVE: SWF',
		'expansion_k'    : 5,
		'language'       : 'en',
		}


class Explorator(Generator):
	""" Class that handles exploration phase.
	"""
	def __init__(
		self,
		embedding_model,
		expansion_embedding_model,
		config
	):
		config = {**default_config, **config}
		super().__init__(embedding_model)

		self.vectors = {}
		self.vectors[config['corona-context']] = np.load(config['corona-vectors'])
		self.vectors[config['swf-context']]    = np.load(config['swf-vectors'])

		self.size = {}
		self.size[config['corona-context']] = self.vectors[config['corona-context']].shape[0]
		self.size[config['swf-context']]    = self.vectors[config['swf-context']].shape[0]

		self.k               = config['expansion_k']
		self.language        = config['language']
		self.expansion_model = expansion_embedding_model

		# Initialize matrix to store distances between motivations (one key per different group_id).
		self.stored_distances = {}

		if self.language == 'en':
			self.stemmer    = PorterStemmer()
			self.lemmatizer = WordNetLemmatizer()

	def compute_center(self, value_id, Value, Keyword):
		""" Get the value cluster center as the normalized sum of the embeddings of the keywords + value name.
		"""
		value = super().compute_center(value_id, Value, Keyword)

		# Reset shown_similar.
		value.shown_similar = 0

	def get_next_motivation(self, Context, UserContext, UserContextMotivation, Value, Motivation, Choice, similar_value_id=None):
		"""
			If requested, return a motivation similar to the indicated value.
			Else, if no motivation was seen yet, return a random one.
			Else, return the next motivation according to Farthest First Traversal algorithm.
		"""
		# Get current user context.
		user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)

		# Get list of seen motivation ids for the current PVE.
		seen_motivation_ids = self.__get_seen_motivation_ids(UserContext, user_context, Motivation)
		if similar_value_id is not None:
			motivation_id, distance = self.__get_next_motivation_closest_to_value(Context, UserContext, Value, Choice, Motivation, UserContextMotivation, similar_value_id)
			distance_type = 'similarity'
		elif not len(seen_motivation_ids):
			motivation_id, distance = self.__get_random_motivation_index(Context, UserContext, Choice, Motivation, UserContextMotivation)
			distance_type = 'fft'
		else:
			motivation_id, distance = self.__farthest_first_traversal(Context, UserContext, Choice, Motivation, UserContextMotivation, Value, seen_motivation_ids)
			distance_type = 'fft'

		if distance_type == 'similarity':
			# Create UserContextMotivation object with similarity distance.
			user_context_motivation = UserContextMotivation(
					user_context_id=user_context.id,
					motivation_id=motivation_id,
					similarity_distance=distance
			)
		else:
			# Create UserContextMotivation object with FFT distance.
			user_context_motivation = UserContextMotivation(
					user_context_id=user_context.id,
					motivation_id=motivation_id,
					fft_distance=distance
			)

		motivation = Motivation.query.get(motivation_id)

		return motivation, user_context_motivation

	def __get_random_motivation_index(self, Context, UserContext, Choice, Motivation, UserContextMotivation):
		""" Return random index of a motivation. Return 100 as fake FFT distance.
		"""
		# Get current context.
		user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
		context = Context.query.get(user_context.context_id).context_name_en
		index = random.randrange(self.size[context])
		motivation_id = self.__get_motivation_id_from_index(Choice, Motivation, user_context.context_id, index)
		return motivation_id, 100

	def __get_seen_motivation_ids(self, UserContext, user_context, Motivation):
		""" Return list of motivations ids seen by current user group id for
			the current context.
		"""
		# Return motivations seen by user context id.
		all_contexts = UserContext.query.filter_by(
			group_id=user_context.group_id, context_id=user_context.context_id)
		seen_motivations = []
		for context in all_contexts.all():
			seen_motivations.extend(context.seen_motivations)

		return [(motivation.motivation_id) for motivation in seen_motivations]

	def __get_motivation_id_from_index(self, Choice, Motivation, context_id, index):
		"""
		Get the motivation object at pve_idx `index` for the current context.
		"""
		choices = Choice.query.filter_by(context_id=context_id).all()
		choice_ids = [choice.id for choice in choices]
		motivations = Motivation.query.filter(Motivation.choice_id.in_(choice_ids))
		motivation = motivations.filter_by(pve_idx=index).first()
		return motivation.id

	def __farthest_first_traversal(self, Context, UserContext, Choice, Motivation, UserContextMotivation, Value, seen_motivation_ids):
		""" Return next motivation index according to Farthest First Traversal algorithm.
		"""
		# Get current context.
		user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
		# Check if seen_motivation_ids motivations distances are already in stored_distances.
		computed_distances = []
		new_ids            = []
		if user_context.group_id in self.stored_distances.keys():
			stored_distances = self.stored_distances[user_context.group_id]
			for motivation_id in seen_motivation_ids:
				if motivation_id in stored_distances.keys():
					computed_distances.append(stored_distances[motivation_id])
				else:
					new_ids.append(motivation_id)
		else:
			self.stored_distances[user_context.group_id] = {}
			new_ids = seen_motivation_ids

		computed_distances = np.array(computed_distances, dtype=np.float)

		# Get current context.
		context = Context.query.get(user_context.context_id).context_name_en

		# Compute distances for new motivations and store them in stored_distances.
		vector_idx = [motivation.pve_idx for motivation in Motivation.query.filter(Motivation.id.in_(new_ids)).all()]
		new_vectors   = self.vectors[context][vector_idx]
		new_distances = np.absolute(cdist(new_vectors, self.vectors[context], 'cosine'))
		for motivation_id, distances in zip(new_ids, new_distances):
			self.stored_distances[user_context.group_id][motivation_id] = distances

		# The traversed set distances are old and new distances.
		if len(computed_distances):
			traversed_set_distances = np.concatenate((computed_distances, new_distances))
		else:
			traversed_set_distances = new_distances

		# If there are value centers, add their distances to the traversed set distances.
		value_query = Value.query.filter_by(submitted_by=user_context.id)
		if len(value_query.all()):
			centers = np.array([np.frombuffer(value.center, dtype=np.float) for value in value_query])
			centers_distances = np.absolute(cdist(centers, self.vectors[context], 'cosine'))
			traversed_set_distances = np.concatenate((traversed_set_distances, centers_distances))

		# The distance between a motivation and a set is the distance
		# between the motivation and the closest point in the traversed set.
		distances = traversed_set_distances.min(axis=0)

		# Store distances and indices in tuples, sort from largest to smallest distance.
		total_distances = list(zip(range(len(distances)), distances))
		total_distances = sorted(total_distances, key=lambda x: x[1], reverse=True)

		# Loop in total_distances tuple until we find an index that has not been shown yet.
		max_index = 0
		all_seen_vector_idx = [motivation.pve_idx for motivation in Motivation.query.filter(Motivation.id.in_(seen_motivation_ids)).all()]
		while total_distances[max_index][0] in all_seen_vector_idx:
			max_index += 1
		show_index = total_distances[max_index][0]
		distance = total_distances[max_index][1]

		motivation_id = self.__get_motivation_id_from_index(Choice, Motivation, user_context.context_id, show_index)
		return motivation_id, distance

	def get_word_expansions(self, seed):
		""" The provided seed word is expanded with the k closest words
			with different stem in the expansion model embedding space. Returns a list of strings.
		"""
		if self.language != 'en':
			return ["Word expansion only supported in English."]

		# Get lemma of each token, excluding stop words and out of vocabulary.
		stop_words = set(stopwords.words('english'))
		tokens = [token for token in word_tokenize(seed.lower()) if not token in stop_words \
				and self.lemmatizer.lemmatize(token) in self.expansion_model.vocab]

		if not len(tokens):
			return []

		# Get stems of the tokens.
		stems = [self.stemmer.stem(token) for token in tokens]

		# Get the seed vector as the average of each token lemma's embeddings.
		vectors     = [self.expansion_model[self.lemmatizer.lemmatize(token)] for token in tokens]
		seed_vector = np.mean(np.array(vectors), axis=0)

		# Find 3 * k most similar words: we want to find at least k words
		# with different lemma from the lemmas of the provided seed.
		similar_words = self.expansion_model.similar_by_vector(seed_vector, topn=(self.k * 3))

		# Loop over the most similar words and find k words with different stems.
		expansions = []
		for word in similar_words:
			if len(expansions) == self.k:
				break
			tokens = [self.stemmer.stem(token) for token in word_tokenize(word[0])]
			if any(token in stems for token in tokens):
				continue
			expansions.append(word[0])

		return expansions

	def __get_next_motivation_closest_to_value(self, Context, UserContext, Value, Choice, Motivation, UserContextMotivation, value_id):
		""" Return n motivations closest to the indicated value.
			Return list of Motivation.
		"""
		# Get current user context.
		user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)

		# Get value from id.
		value_query = Value.query.filter_by(id=value_id, submitted_by=user_context.id)
		if len(value_query.all()) != 1:
			return

		# Get current context name.
		context = Context.query.get(user_context.context_id).context_name_en

		# Get value center.
		center = np.frombuffer(value_query.first().center, dtype=np.float)

		# Compute cosine distance between center and all motivations vectors.
		distances = cdist([center], self.vectors[context], 'cosine')[0]

		# Store distances and indices in tuples, sort from smallest to largest distance.
		distances = zip(range(len(distances)), distances)
		distances = sorted(distances, key=lambda x: x[1])

		# Get number of similar motivations that have already been shown.
		shown_similar = value_query.first().shown_similar

		# Get closest motivations not seen by the user in this context.
		index, distance = distances[shown_similar]
		motivation_id = self.__get_motivation_id_from_index(Choice, Motivation, user_context.context_id, index)
		while len(UserContextMotivation.query.filter_by(motivation_id=motivation_id).all()):
			shown_similar += 1
			index, distance = distances[shown_similar]
			motivation_id = self.__get_motivation_id_from_index(Choice, Motivation, user_context.context_id, index)

		# Increment number of shown similar motivations.
		value_query.first().shown_similar = shown_similar

		return motivation_id, distance

	def get_history(self, UserContext, UserContextMotivation, Motivation, Action, AnnotationAction):
		""" Parse annotation actions and return data in a format for plotting.
		"""
		# Get current user's annotations sorted by time stamp.
		user_context_id = UserContext.get_user_context(current_user.id, current_user.working_context_id).id

		# Get annotations completed by current user in current context.
		annotations = AnnotationAction.query.filter_by(completed_by=user_context_id)
		annotations = annotations.order_by(AnnotationAction.created_on.asc())
		if not len(annotations.all()):
			return [], [], []

		# Get sorted unique motivations ID's.
		motivations_ids = []
		for annotation in annotations.all():
			if annotation.shown_motivation not in motivations_ids:
				motivations_ids.append(annotation.shown_motivation)

		# Get FFT distances.
		motivations_ids, distances = self.__parse_distances(Motivation, UserContextMotivation, motivations_ids, user_context_id)

		# Get colors vector.
		colors = self.__match_actions_to_colors(motivations_ids, distances, Action, AnnotationAction, user_context_id)

		# The x-axis is the order in which motivations have been shown.
		x_axis = list(range(len(distances)))

		# The y-axis are the distances, independently of FFT or similarity.
		y_axis = [distance[0] for distance in distances]

		return x_axis, y_axis, colors

	def __parse_distances(self, Motivation, UserContextMotivation, motivations_ids, user_context_id):
		""" Parse distances. Remove initial random motivation with fake FFT distance.
			Return tuple (distance, type), where the type is FFT or similarity distance.
		"""
		# Get sorted shown motivations.
		#motivations = [Motivation.query.get(motivation_id) for motivation_id  in motivations_ids]
		uc_motivations = []
		for motivation_id in motivations_ids:
			uc_motivation = UserContextMotivation.query.filter_by(motivation_id=motivation_id)
			uc_motivation = uc_motivation.filter_by(user_context_id=user_context_id)
			if len(uc_motivation.all()) != 1:
				print("Warining: too many links between UserContextMotivation and Motivation. Using the first")
			uc_motivations.append(uc_motivation.first())

		# Get FFT distances of the motivations seen by the current user.
		distances = [(motivation.fft_distance, 'fft') if motivation.fft_distance \
				else (motivation.similarity_distance, 'sim') for motivation in uc_motivations]

		for index, (distance, kind) in enumerate(distances):
			if distance == 100 and kind == 'fft':
				del(distances[index])
				del(motivations_ids[index])

		return motivations_ids, distances

	def __match_actions_to_colors(self, motivations_ids, distances, Action, AnnotationAction, user_context_id):
		""" Get colors matching annotation actions of the current user.
		"""
		colors = []
		for motivation_id, distance in zip(motivations_ids, distances):
			annotations = AnnotationAction.query.filter_by(shown_motivation=motivation_id)
			annotations = annotations.filter_by(completed_by=user_context_id).all()
			if distance[1] == 'sim':
				colors.append(color_map['similarity'])
			elif len(annotations) == 1:
				if annotations[0].action == Action.ADD_VALUE:
					colors.append(color_map['add_value'])
				elif annotations[0].action == Action.ADD_KEYWORD:
					colors.append(color_map['add_keyword'])
				elif annotations[0].action == Action.REMOVE_VALUE:
					colors.append(color_map['remove_value'])
				elif annotations[0].action == Action.REMOVE_KEYWORD:
					colors.append(color_map['remove_keyword'])
				elif annotations[0].action == Action.SKIP_MOTIVATION_ALREADY_PRESENT:
					colors.append(color_map['already_present'])
				elif annotations[0].action == Action.SKIP_MOTIVATION_UNCOMPREHENSIBLE or \
						annotations[0].action == Action.SKIP_MOTIVATION_NO_VALUE:
					colors.append(color_map['generic_skip'])
			elif len(annotations) > 1:
				if all([annotation.action in [Action.ADD_VALUE, Action.ADD_KEYWORD] \
						for annotation in annotations]):
					colors.append(color_map['add_many'])
				elif all([annotation.action in [Action.REMOVE_VALUE, Action.REMOVE_KEYWORD] \
						for annotation in annotations]):
					colors.append(color_map['remove_many'])
				else:
					colors.append(color_map['multi_actions'])
			else:
				colors.append(color_map['no_action'])  # should never be invoked

		return colors

