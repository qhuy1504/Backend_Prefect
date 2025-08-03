from flask import Blueprint
from controllers import admin_controller
from middlewares.authenticate import login, require_api_key
from middlewares.upload import upload_file

admin_bp = Blueprint('admin_bp', __name__)

# User routes
admin_bp.route('/users', methods=['POST'])(require_api_key(upload_file(admin_controller.create_user)))
admin_bp.route('/users', methods=['GET'])(require_api_key(admin_controller.list_users))
admin_bp.route('/users/<int:user_id>', methods=['DELETE'])(require_api_key(admin_controller.delete_user))
admin_bp.route('/users/<int:user_id>', methods=['PUT'])(require_api_key(upload_file(admin_controller.update_user)))
admin_bp.route('/users/<int:user_id>', methods=['GET'])(require_api_key(admin_controller.get_user_by_id))
admin_bp.route('/login', methods=['POST'])(require_api_key(login))

# Group routes
admin_bp.route('/groups', methods=['POST'])(require_api_key(admin_controller.create_group))
admin_bp.route('/groups', methods=['GET'])(require_api_key(admin_controller.list_groups))
admin_bp.route('/groups/<int:group_id>', methods=['DELETE'])(require_api_key(admin_controller.delete_group))
admin_bp.route('/groups/<int:id>', methods=['PUT'])(require_api_key(admin_controller.update_group))

# Role routes
admin_bp.route('/roles', methods=['POST'])(require_api_key(admin_controller.create_role))
admin_bp.route('/roles', methods=['GET'])(require_api_key(admin_controller.list_roles))
admin_bp.route('/roles/<int:role_id>', methods=['DELETE'])(require_api_key(admin_controller.delete_role))
admin_bp.route('/roles/<int:role_id>', methods=['PUT'])(require_api_key(admin_controller.update_role))

# Menu routes
admin_bp.route('/menus', methods=['POST'])(require_api_key(admin_controller.create_menu))
admin_bp.route('/menus', methods=['GET'])(require_api_key(admin_controller.list_menus))
admin_bp.route('/menus/<int:id>', methods=['DELETE'])(require_api_key(admin_controller.delete_menu))
admin_bp.route('/menus/<int:id>', methods=['PUT'])(require_api_key(admin_controller.update_menu))

# Assign user to group
admin_bp.route('/user-group/<int:user_id>', methods=['POST'])(require_api_key(admin_controller.assign_groups_to_user))
admin_bp.route('/user-groups', methods=['GET'])(require_api_key(admin_controller.get_users_with_groups))
admin_bp.route('/user-group/remove', methods=['DELETE'])(require_api_key(admin_controller.remove_user_from_group))

# Assign role to group
admin_bp.route('/group-roles/<int:group_id>', methods=['POST'])(require_api_key(admin_controller.assign_roles_to_group))
admin_bp.route('/group-roles', methods=['GET'])(require_api_key(admin_controller.get_roles_with_groups))
admin_bp.route('/groupid-role/<int:group_id>', methods=['GET'])(require_api_key(admin_controller.get_roles_of_group_with_group_id))
admin_bp.route('/group-role/remove', methods=['DELETE'])(require_api_key(admin_controller.remove_role_from_group))
admin_bp.route('/groupid-roles/<int:group_id>', methods=['POST'])(require_api_key(admin_controller.update_roles_of_group))

# Assign menu to role
admin_bp.route('/role-menu/<int:role_id>', methods=['POST'])(require_api_key(admin_controller.assign_menus_to_role))
admin_bp.route('/role-menus', methods=['GET'])(require_api_key(admin_controller.get_role_menus))
admin_bp.route('/role-menu/<int:role_id>', methods=['DELETE'])(require_api_key(admin_controller.remove_menu_from_role))
admin_bp.route('/role-menus/<int:role_id>', methods=['POST'])(require_api_key(admin_controller.update_menus_of_role))
