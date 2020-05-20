#!/usr/bin/env python3

import itertools


class Node:
    def __init__(self, node_type, width, rows, times):
        self.node_type = node_type
        self.width = width
        self.rows = rows
        self.times = times
        self.inputs = []
        self.parent = None

    def as_dict(self):
        return {
            'type': self.node_type,
            'width': self.width,
            'rows': self.rows,
            'times': self.times,
            'inputs': [ x.as_dict() for x in self.inputs ],
        }


def indent_of_line(line):
    return sum(1 for _ in itertools.takewhile(str.isspace, line))

def line_is_node(line):
    return line_is_root(line) or line_is_child(line)

def line_is_child(line):
    return line.lstrip().startswith('-> ')

def line_is_root(line):
    return indent_of_line(line) == 1

def node_type(line):
    return (
        line
        .split('->', 1)[-1]
        .split('(', 1)[0]
        .split(' on ', 1)[0]
        .strip()
    )

def node_width(line):
    return int(
        line
        .split(' width=', 1)[1]
        .split(')', 1)[0]
    )

def node_rows(line):
    return int(
        line
        .split(' rows=', 2)[2]
        .split(' ', 1)[0]
    )

def node_times(line):
    # microseconds
    parts = (
        line
        .split('actual time=', 1)[1]
        .split(' ', 1)[0]
        .split('..')
    )
    return [ int(1000 * float(n)) for n in parts ]

def parse(text):
    last_indent = 0
    indent = 0
    root = None
    node = None

    for line in text.splitlines():
        if line.strip() == 'QUERY PLAN':
            continue
        if line.strip() == '-'*len(line.strip()):
            continue
        if not line.strip():
            continue

        # analyze indent and traverse the graph as needed
        if line_is_root(line):
            last_indent = indent
            indent = indent_of_line(line)
            assert indent == 1
            assert node is None

            node = Node(node_type(line), node_width(line), node_rows(line), node_times(line))
            root = node
        elif line_is_child(line):
            last_indent = indent
            indent = indent_of_line(line)
            assert indent > 1
            assert indent % 2 == 1
            assert node is not None

            if indent == last_indent:
                child = Node(node_type(line), node_width(line), node_rows(line), node_times(line))
                child.parent = node.parent
                node.parent.inputs.append(child)
                node = child
            elif indent > last_indent:
                child = Node(node_type(line), node_width(line), node_rows(line), node_times(line))
                child.parent = node
                node.inputs.append(child)
                node = child
            elif indent < last_indent:
                diff = last_indent - indent
                while diff:
                    node = node.parent
                    diff -= 6
                child = Node(node_type(line), node_width(line), node_rows(line), node_times(line))
                child.parent = node.parent
                node.parent.inputs.append(child)
                node = child
        else: # it's details of the current node
            pass

    return root

if __name__ == '__main__':
    import pprint
    with open('example-plan.txt') as f:
        pprint.pprint(parse(f.read()).as_dict())
