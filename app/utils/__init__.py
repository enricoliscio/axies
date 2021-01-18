# from flask import session
# from flask_login import current_user
#
# def get_user_context_id():
#     """Get user context id from current user and session.
#     """
#     user_contexts = current_user.contexts_assigned()
#     current_context_id = session['current_context_id']
#     active_context = user_contexts.filter_by(context_id=current_context_id)
#     if len(active_context.all()) != 1:
#         return
#
#     # active_context is a tuple: (Context, UserContext)
#     return active_context.first()[1].id