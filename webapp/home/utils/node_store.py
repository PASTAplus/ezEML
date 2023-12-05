"""
Node store utilities used in troubleshooting issues with the node store.
"""

from flask import request

from metapype.model.node import Node
from webapp.home.home_utils import log_error, log_info


def node_tree_ids(node: Node, ids: list):
    """ Return a list of node IDs for all nodes in the subtree rooted at node. """
    ids.append(node.id)
    for child in node.children:
        node_tree_ids(child, ids)
    return ids


def calculate_node_store_checksums(eml_node):
    """ Calculate checksums for node IDs in the node store and the node tree. Trouble-shooting aid. """
    import hashlib
    id_string = ''
    for key, val in sorted(Node.store.items()):
        id_string += val.id
    node_store_hash = hashlib.md5(id_string.encode('utf-8')).hexdigest()
    tree_ids = sorted(node_tree_ids(eml_node, []))
    tree_hash = hashlib.md5(''.join(tree_ids).encode('utf-8')).hexdigest()
    return node_store_hash, tree_hash


def dump_node_store(eml_node, prefix=''):
    """ For use in debugging. """

    def dump_node(node: Node, indent=0):
        indent_str = ' ' * indent
        print(f'{indent_str}{node.name} {node.id} {node.content}')
        for child in node.children:
            dump_node(child, indent + 2)

    dump_node(eml_node)
    store_len = len(Node.store)
    log_info(f'*** {prefix} store_len={store_len}     {request.url}')
    node_store_hash, tree_hash = calculate_node_store_checksums(eml_node)
    log_info(f'*** {prefix} node store checksum={node_store_hash}    {request.url}')
    log_info(f'*** {prefix}  node tree checksum={tree_hash}    {request.url}')


def calculate_node_store_checksum():
    """
    Calculate checksum for concatenation of all sorted node IDs in the node store. Trouble-shooting aid.
    """
    import hashlib
    id_string = ''
    for key, val in sorted(Node.store.items()):
        id_string += val.id
    return hashlib.md5(id_string.encode('utf-8')).hexdigest()