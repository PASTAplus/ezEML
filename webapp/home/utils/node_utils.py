"""
Helper functions for accessing the Metapype model.
"""

import typing as ty
from enum import Enum

from metapype.eml import names, rule
from metapype.model.node import Node


class Optionality(Enum):
    REQUIRED = 1
    OPTIONAL = 2
    FORCE = 3


def new_child_node(child_name:str, parent:Node, content:str=None, attribute:ty.Tuple[str,str]=None, force=False):
    """
    Create a new child node and add it to the parent node. Optionally, set its content and/or an attribute.
    Return the new child node.
    If force is True, add the child node without checking the parent's rule. Used for additionalMetadata.
    """
    child_node = Node(child_name, parent=parent)
    if content is not None:
        child_node.content = content
    if attribute is not None:
        child_node.add_attribute(attribute[0], attribute[1])
    if not force:
        add_child(parent, child_node)
    else:
        parent.add_child(child_node)
    return child_node


def add_node(parent_node:Node, child_name:str, content:str=None, optionality=Optionality.REQUIRED):
    """
    Add a child node to the parent node.
    Optionality is used as follows:
        OPTIONAL: If content is None, do not add the child node. Otherwise, add the child node.
                This saves the caller from having to check the content for None.
        REQUIRED: Add the child node if the parent's rule allows it, and set the content.
                If the child cannot validly be added to the parent, raise an exception.
        FORCE: Add the child node without checking the parent's rule, and set the content.
                This is used when we are adding an additionalMetadata node, for example, for which there is no rule.
    """
    if optionality == Optionality.OPTIONAL and not content:
        return
    child_node = parent_node.find_child(child_name)
    if not child_node:
        child_node = Node(child_name, parent=parent_node)
        if not Optionality.FORCE:
            add_child(parent_node, child_node)
        else:
            # When we add to additionalMetadata, for example, we sidestep rule checking
            parent_node.add_child(child_node)
    child_node.content = content
    if not child_node.nsmap:
        child_node.nsmap = parent_node.nsmap
    return child_node


def add_child(parent_node:Node, child_node:Node):
    """
    Add a child node to the parent node, using the Metapype rule for the parent to determine the valid insertion point.
    If the child is not an allowed child of the parent, Metapype will raise an exception.
    """
    if parent_node and child_node:
        parent_rule = rule.get_rule(parent_node.name)
        index = parent_rule.child_insert_index(parent_node, child_node)
        if not child_node.nsmap:
            child_node.nsmap = parent_node.nsmap
        parent_node.add_child(child_node, index=index)


def remove_child(child_node:Node):
    """
    Remove the given child node from its parent.
    """
    if child_node:
        parent_node = child_node.parent
        if parent_node:
            parent_node.remove_child(child_node)


def replace_node(new_node:Node, old_node_id:str):
    """
    If the old_node_id is not '1', replace the old node with the new node.
    This is used on pages that support Save Changes, where we want the modified node to replace the original node,
     using the same node ID so the Back button works as expected.
    """
    if old_node_id and old_node_id != '1':
        old_node = Node.get_node_instance(old_node_id)
        if old_node:
            parent_node = old_node.parent
            if parent_node:
                # Make the replacement in the node tree
                parent_node.replace_child(old_node, new_node, delete_old=False)
                # Make the replacement in the node instance dictionary
                new_node_id = new_node.id
                new_node._id = old_node.id
                Node.set_node_instance(new_node)
                Node.delete_node_instance(id=new_node_id)


def get_unit_text(attribute_node):
    unit_text = None
    standard_unit_node = attribute_node.find_descendant(names.STANDARDUNIT)
    if standard_unit_node:
        unit_text = standard_unit_node.content.strip().lower()
    if custom_unit_node := attribute_node.find_descendant(names.CUSTOMUNIT):
        unit_text = custom_unit_node.content.strip().lower()
    return unit_text
