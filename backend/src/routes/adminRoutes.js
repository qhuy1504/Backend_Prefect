// routes/adminRoutes.js
import express from 'express';
import {
    createUser, listUsers, deleteUser, updateUser, getUserById,
    createGroup, listGroups, deleteGroup, updateGroup,
    createRole, listRoles, deleteRole, updateRole,
    createMenu, listMenus, deleteMenu, updateMenu, assignMenusToRole, updateMenusOfRole,
    removeUserFromGroup,
    removeRoleFromGroup,
    removeMenuFromRole,
    getUserGroups, assignGroupsToUser, getGroupRoles,
    assignRolesToGroup, getRoleMenus,
    getUsersWithGroups, getRolesWithGroups, getRolesOfGroupWithGroupId,
    updateRolesOfGroup

} from '../controllers/adminController.js';
import { login } from '../middlewares/authenticate.js';
import { upload } from '../middlewares/upload.js';

const router = express.Router();

// User routes
router.post('/users', upload.single('avatar'), createUser);
router.get('/users', listUsers);
router.delete('/users/:id', deleteUser);
router.put("/users/:id", upload.single("avatar"), updateUser);
router.get('/users/:id', getUserById);
router.post('/login', login);

// Group routes
router.post('/groups', createGroup);
router.get('/groups', listGroups);
router.delete('/groups/:id', deleteGroup);
router.put('/groups/:id', updateGroup);

// Role routes
router.post('/roles', createRole);
router.get('/roles', listRoles);
router.delete('/roles/:id', deleteRole);
router.put('/roles/:id', updateRole);

// Menu routes
router.post('/menus', createMenu);
router.get('/menus', listMenus);
router.delete('/menus/:id', deleteMenu);
router.put('/menus/:id', updateMenu);

// Assignments user to group
router.post('/user-group/:id', assignGroupsToUser);
router.get('/user-groups', getUsersWithGroups);
router.delete('/user-group/remove', removeUserFromGroup);

// Assignments group to role
router.post('/group-roles/:id', assignRolesToGroup);
router.get('/group-roles', getRolesWithGroups);
router.get('/groupid-role/:id', getRolesOfGroupWithGroupId);
router.delete('/group-role/remove', removeRoleFromGroup);
router.post('/groupid-roles/:id', updateRolesOfGroup); 

// Assignments role to menu

router.post('/role-menu/:id', assignMenusToRole);
router.get('/role-menus', getRoleMenus);
router.delete('/role-menu/:role_id', removeMenuFromRole);
router.post('/role-menus/:id', updateMenusOfRole);



export default router;
