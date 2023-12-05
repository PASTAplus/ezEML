"""
Helper functions for accessing the Metapype model.
"""

import typing as ty
from enum import Enum

from metapype.eml import rule
from metapype.model.node import Node


class Optionality(Enum):
    REQUIRED = 1
    OPTIONAL = 2
    FORCE = 3


def new_child_node(child_name:str, parent:Node, content:str=None, attribute:ty.Tuple[str,str]=None):
    """
    Create a new child node and add it to the parent node. Optionally, set its content and/or an attribute.
    Return the new child node.
    """
    child_node = Node(child_name, parent=parent)
    if content is not None:
        child_node.content = content
    if attribute is not None:
        child_node.add_attribute(attribute[0], attribute[1])
    add_child(parent, child_node)
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
    return child_node


def add_child(parent_node:Node, child_node:Node):
    """
    Add a child node to the parent node, using the Metapype rule for the parent to determine the valid insertion point.
    If the child is not an allowed child of the parent, Metapype will raise an exception.
    """
    if parent_node and child_node:
        parent_rule = rule.get_rule(parent_node.name)
        index = parent_rule.child_insert_index(parent_node, child_node)
        parent_node.add_child(child_node, index=index)


def remove_child(node:Node):
    """
    Remove the given child node from its parent.
    """
    node_id = node.id
    if node_id:
        child_node = Node.get_node_instance(node_id)
        if child_node:
            parent_node = child_node.parent
            if parent_node:
                parent_node.remove_child(child_node)
