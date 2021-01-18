from .utils import csd_color_map
from .generator import Generator

import itertools
import numpy as np
from scipy.spatial.distance import cdist

from flask_login import current_user


class Consolidator(Generator):
	""" Class that handles Consolidation phase.
	"""
	def __init__(self, embedding_model):
		super().__init__(embedding_model)

	def make_consolidation_values(self, UserContext, Value, ConsolidationValue):
		""" Create ConsolidationValues list with all values from UserContext's in the same group.
		"""
		# Get user contexts in the same group and same context as the current user context.
		group_id, context_id = self.__get_group_context_ids(UserContext)
		user_contexts = UserContext.query.filter_by(group_id=group_id, context_id=context_id).all()
		if not len(user_contexts):
			print("Could not find users in this group.")
			return []

		# Get user context ids.
		user_context_ids = [user_context.id for user_context in user_contexts]

		# Get values from user contexts ids.
		values = Value.query.filter(Value.submitted_by.in_(user_context_ids)).all()
		if not len(values):
			return []

		# Create list of ConsolidationValue.
		consolidation_values = self.__consolidation_values_from_values(ConsolidationValue, values, group_id, context_id)

		return values, consolidation_values

	def make_consolidation_keywords(self, UserContext, ConsolidationValue, Keyword, ConsolidationKeyword):
		""" Create list of ConsolidationKeyword from the source values of the ConsolidationValues.
		"""
		# Get group and context ids.
		group_id, context_id = self.__get_group_context_ids(UserContext)

		# Get all ConsolidationValues with this group and context ids.
		values = ConsolidationValue.query.filter_by(group_id=group_id, context_id=context_id).all()

		# Make list of (ConsolidationValue, Keyword) tuples.
		values_and_keywords = []
		for value in values:
			source_value = value.source_values.first()
			values_and_keywords.append((value, Keyword.query.filter_by(value=source_value.value_id).all()))

		# Make list of ConsolidationKeywords.
		consolidation_keywords = []
		for value, keywords in values_and_keywords:
			for keyword in keywords:
				cons_keyword = ConsolidationKeyword(name=keyword.name, group_id=group_id,
					context_id=context_id, value=value.id)
				consolidation_keywords.append(cons_keyword)

		return consolidation_keywords

	def make_value_couples(self, ValueCouple, consolidation_values):
		""" Create ValueCouple list from consolidation values.
		"""
		# Generate all values combinations.
		couples = itertools.combinations(consolidation_values, 2)

		# Get list of ValueCouple.
		value_couples = self.__get_value_couple_list(couples, ValueCouple)

		return value_couples

	def get_next_value_couple(self, ValueCouple, UserContext):
		""" Get not yet shown ValueCouple with smallest distance.
		"""
		# Get group and context ids.
		group_id, context_id = self.__get_group_context_ids(UserContext)

		# Get all not shown ValueCouple from this group context.
		value_couples = ValueCouple.from_context_group(context_id, group_id)
		value_couples = value_couples.filter_by(already_shown=False)
		if not len(value_couples.all()):
			print("All couples have been shown.")
			return None

		# Sort value couples from smallest to largest distance, get the first.
		couple = value_couples.order_by(ValueCouple.distance.asc()).first()

		# Set the smallest distance couple as shown and return it.
		couple.already_shown = True

		return couple

	def make_new_value_couples(self, value_id, UserContext, ValueCouple, ConsolidationValue):
		""" Given a new value id, create new value couples with that value.
		"""
		# Get group and context ids.
		group_id, context_id = self.__get_group_context_ids(UserContext)

		# Get values from user contexts.
		values = ConsolidationValue.query.filter_by(group_id=group_id, context_id=context_id).all()
		if not len(values):
			return []

		# Pop the value with value_id from the values list.
		value_index = values.index(ConsolidationValue.query.get(value_id))
		new_value = values.pop(value_index)

		# Create list of Value couples tuples.
		new_couples = list(itertools.product([new_value], values))

		# Return list of ValueCouple.
		return self.__get_value_couple_list(new_couples, ValueCouple)

	def update_value_couples(self, value_id, ValueCouple, ConsolidationValue, ConsolidationKeyword):
		""" Given a value id, update the center of the value, update the couples distances
			that have that value id and set all couples with that id as not shown.
		"""
		# Update the center of the value.
		self.compute_center(value_id, ConsolidationValue, ConsolidationKeyword)

		# Get all value couples that contain the value.
		value_couples = ValueCouple.containing_value(value_id).all()
		if not len(value_couples):
			return

		# Update distances and set value couple as not shown.
		for value_couple in value_couples:
			self.__update_couple_distance(value_couple, ConsolidationValue)
			value_couple.already_shown = False

	def delete_value_couples(self, ValueCouple, value_id):
		""" Given a value id, delete all ValueCouple containing the value.
		"""
		ValueCouple.containing_value(value_id).delete()

	def get_trigger_sentences(self, value_id, ValueConsolidationValue, AnnotationAction, Action, Motivation):
		""" Return motivations that led to an annotation action on the value.
		"""
		# Get Value ids from ValueConsolidationValues with the provided ConsolidationValue id.
		vcvs = ValueConsolidationValue.query.filter_by(consolidation_value_id=value_id)
		value_ids = [vcv.value_id for vcv in vcvs.all()]
		if not len(value_ids):
			return []

		# Get value and keyword addition annotation actions with the Value id.
		annotations = AnnotationAction.query.filter(AnnotationAction.value.in_(value_ids))
		annotations = annotations.filter(
				(AnnotationAction.action == Action.ADD_VALUE) | (AnnotationAction.action == Action.ADD_KEYWORD))
		if not len(annotations.all()):
			return []

		# Get unique motivations ID's.
		motivations_ids = []
		for annotation in annotations.all():
			if annotation.shown_motivation not in motivations_ids:
				motivations_ids.append(annotation.shown_motivation)

		return [Motivation.query.get(mot_id) for mot_id in motivations_ids]

	def __get_group_context_ids(self, UserContext):
		""" Get user contexts in the same group and same context as the current user context.
		"""
		user_context = UserContext.get_user_context(current_user.id, current_user.working_context_id)
		return user_context.group_id, user_context.context_id

	def __consolidation_values_from_values(self, ConsolidationValue, values, group_id, context_id):
		""" From a list of Value, create a list of ConsolidationValue.
		"""
		consolidation_values = []
		for value in values:
			cons_value = ConsolidationValue(name=value.name, group_id=group_id,
					context_id=context_id, center=value.center)
			consolidation_values.append(cons_value)

		return consolidation_values

	def __get_value_couple_list(self, couples, ValueCouple):
		""" Return a ValueCouple list from a list of ConsolidationValue tuples.
		"""
		value_couples = []
		for couple in couples:
			# Get centers and compute distance.
			center_0 = np.expand_dims(np.frombuffer(couple[0].center, dtype=np.float), axis=0)
			center_1 = np.expand_dims(np.frombuffer(couple[1].center, dtype=np.float), axis=0)
			distance = np.absolute(cdist(center_0, center_1, 'cosine'))[0]

			value_couples.append(ValueCouple(
				value_id_0=couple[0].id,
				value_id_1=couple[1].id,
				distance=distance
				))

		return value_couples

	def __update_couple_distance(self, value_couple, ConsolidationValue):
		""" Update the distance between a couple of values.
		"""
		# Get values.
		value_0 = ConsolidationValue.query.get(value_couple.value_id_0)
		value_1 = ConsolidationValue.query.get(value_couple.value_id_1)

		# Get value centers.
		center_0 = np.expand_dims(np.frombuffer(value_0.center, dtype=np.float), axis=0)
		center_1 = np.expand_dims(np.frombuffer(value_1.center, dtype=np.float), axis=0)

		# Update value couple distance.
		value_couple.distance = np.absolute(cdist(center_0, center_1, 'cosine'))[0]

	def get_history(self, UserContext, CSDAction, ConsolidationAction, ShownValueCouple):
		""" Parse annotation actions and return data in a format for plotting.
		"""
		# Get group and context ids.
		group_id, context_id = self.__get_group_context_ids(UserContext)

		# Get actions completed by current group in current context.
		actions = ConsolidationAction.query.filter_by(group_id=group_id, context_id=context_id)
		actions = actions.order_by(ConsolidationAction.created_on.asc())
		if not len(actions.all()):
			return [], [], []

		# Get sorted unique shown value couples ID's.
		shown_couple_ids = []
		for action in actions.all():
			if action.shown_couple not in shown_couple_ids:
				shown_couple_ids.append(action.shown_couple)

		# Get couple distances.
		distances = [ShownValueCouple.query.get(couple_id).distance for couple_id in shown_couple_ids]

		# Get colors vector.
		colors = self.__match_actions_to_colors(shown_couple_ids, distances, CSDAction, ConsolidationAction, group_id, context_id)

		# The x-axis is the order in which motivations have been shown.
		x_axis = list(range(len(distances)))

		return x_axis, distances, colors

	def __match_actions_to_colors(self, shown_couple_ids, distances, CSDAction, ConsolidationAction, group_id, context_id):
		""" Get colors matching annotation actions of the current user.
		"""
		colors = []
		for couple_id, distance in zip(shown_couple_ids, distances):
			actions = ConsolidationAction.query.filter_by(
					shown_couple=couple_id, group_id=group_id, context_id=context_id).all()
			for index, action in enumerate(actions):
				if action.csd_action == CSDAction.SKIP_COUPLE:
					del(actions[index])
			if len(actions) == 1:
				if actions[0].csd_action == CSDAction.ADD_VALUE:
					colors.append(csd_color_map['add_value'])
				elif actions[0].csd_action == CSDAction.ADD_KEYWORD:
					colors.append(csd_color_map['add_keyword'])
				elif actions[0].csd_action == CSDAction.REMOVE_VALUE:
					colors.append(csd_color_map['remove_value'])
				elif actions[0].csd_action == CSDAction.REMOVE_KEYWORD:
					colors.append(csd_color_map['remove_keyword'])
				elif actions[0].csd_action == CSDAction.MERGE_COUPLE:
					colors.append(csd_color_map['merge'])
			elif len(actions) > 1:
				if all([action.csd_action in [CSDAction.ADD_VALUE, CSDAction.ADD_KEYWORD] \
						for action in actions]):
					colors.append(csd_color_map['add_many'])
				elif all([action.csd_action in [CSDAction.REMOVE_VALUE, CSDAction.REMOVE_KEYWORD] \
						for action in actions]):
					colors.append(csd_color_map['remove_many'])
				else:
					colors.append(csd_color_map['multi_actions'])
			else:
				colors.append(csd_color_map['skip'])

		return colors

