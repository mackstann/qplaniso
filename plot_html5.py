#!/usr/bin/env python3

# disclaimer: this code is a mess.

import colorsys
import sys
import itertools

from qplan.parse import parse


def flatten(graph):
    return [graph] + list(itertools.chain(*[flatten(n) for n in graph.inputs]))


def render(graph):
    print('''
        <html><head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/isomer/0.2.6/isomer.min.js"></script>
        <script>
        document.addEventListener("DOMContentLoaded", function(){
            var iso = new Isomer(document.getElementById("art"));

            var Shape = Isomer.Shape;
            var Point = Isomer.Point;
            var Color = Isomer.Color;
            var Path = Isomer.Path;

            for (x = 0; x < 20; x++) {
              iso.add(new Path([
                new Point(x, 0, 0),
                new Point(x, 19, 0),
                new Point(x, 0, 0)
              ]), new Color(60, 60, 60, 0.1));
            }
            for (y = 0; y < 20; y++) {
              iso.add(new Path([
                new Point(0, y, 0),
                new Point(19, y, 0),
                new Point(0, y, 0)
              ]), new Color(140, 140, 140, 0.1));
            }
    ''')

    # work around zeroes
    for node in flatten(graph):
        if node.width == 0:
            node.width = 1
        if node.times[1] == 0:
            node.times[1] = 1

    max_width = 0.0
    max_depth = 0.0
    max_height = 0.0
    for node in flatten(graph):
        max_width = max(max_width, node.width)
        max_depth = max(max_depth, node.times[1])
        max_height = max(max_depth, node.rows)

    '''
    x = width = columns
    y = height = rows
    z = depth = time

    pre-calculate:
        recurse
          each node gets the maxwidth of the sum of its childrens' maxwidths
          each child gets the x offset of the sum of its left siblings' maxwidths, plus the x offset of its parent

    render:
        recurse
          render each
          z offset is based on time
          x offset is based on calc'd x offset

    xx
    xx
    xx  aa
    ooooaa
    ooooaa
    ooooaa
    xxxxxxxx
    '''

    # monkeypatch
    def set_maxwidth(node, depth=0):
        if node.inputs:
            for n in node.inputs:
                set_maxwidth(n, depth+1) # recurse
            node.maxwidth = max([node.width] + [n.maxwidth for n in node.inputs])
        else:
            # leaf
            node.maxwidth = node.width
    set_maxwidth(graph)

    # monkeypatch
    def set_xoffset(node):
        if not node.parent:
            node.xoffset = 0 # root
        if node.inputs:
            x = node.xoffset + node.maxwidth + 200
            if len(node.inputs) == 1 and node.inputs[0].times[1] <= node.times[0]:
                # they're a sequential chain; don't offset to the side
                x = node.xoffset
            for n in node.inputs:
                n.xoffset = x
                x += n.maxwidth + 200
                set_xoffset(n) # recurse
    set_xoffset(graph)

    ## monkeypatch
    #def set_hue(node, depth=0):
    #    if not node.parent:
    #        node.hue = 0.33
    #    if node.inputs:
    #        half_round_dn = int(min(1, len(node.inputs)/2))
    #        half_round_up = int(min(1, len(node.inputs)/2)+1)
    #        lefts = node.inputs[:half_round_dn]
    #        rights = node.inputs[half_round_dn:]
    #        one_side_range = 0.1
    #        for i in range(depth):
    #            one_side_range /= 1.2
    #        dead_space = one_side_range/2
    #        step = one_side_range/half_round_up
    #        lefts.reverse()
    #        for i in range(half_round_up):
    #            if i < len(lefts):
    #                lefts[i].hue = (node.hue - dead_space - step) % 1
    #            if i < len(rights):
    #                rights[i].hue = (node.hue + dead_space + step) % 1
    #        for n in node.inputs:
    #            set_hue(n, depth=depth+1) # recurse
    def set_hue(node, depth=0):
        node.hue = 0.33 + depth*0.1
        for n in node.inputs:
            set_hue(n, depth+1)
    set_hue(graph)

    def streamable(node):
        return node.node_type in (
            # TODO incomplete
            'Seq Scan',
            'Index Scan',
            'Index Only Scan',
        )
    def calc_immediate_start(node):
        for n in node.inputs:
            calc_immediate_start(n)
        if not node.inputs:
            node.immediate_start = True
        elif (node.inputs and
                all(n.immediate_start for n in node.inputs) and
                all(streamable(n) for n in node.inputs)):
            node.immediate_start = True
        else:
            node.immediate_start = False
    calc_immediate_start(graph)

    def debug(node, depth=0):
        if node.inputs:
            for n in node.inputs:
                debug(n, depth+1)
        print(("."*depth) + (' maxwidth=%d, rows=%d, xoffset=%d, zoffset=%f, hue=%f, immediate_start=%r' % (
            node.maxwidth, node.rows, node.xoffset, node.times[0], node.hue, node.immediate_start)))

    # TODO: is it doing work initially? yes/no -- this determines whether z offset is 0 or times[0].
    # if leaf: yes
    # if all inputs are streaming: yes

    #for node in flatten(graph):
    #    print('maxwidth: %f xoffset: %f inputs: %d' % (node.maxwidth, node.xoffset, len(node.inputs)))

    # TODO: Planning time!
    # TODO: when loops>1, the times are averages. multiply them by #loops

    for node in sorted(flatten(graph), key=lambda n: (-n.xoffset, n.times[0])):
        width = node.width
        depth = node.times[1] if node.immediate_start else node.times[1]-node.times[0]
        height = node.rows
        x_offset = node.xoffset

        z_offset = 0 if node.immediate_start else node.times[0]

        scale = 1/600
        width *= scale
        height *= scale
        depth *= scale
        z_offset *= scale
        x_offset *= scale

        alpha = 0.2

        r, g, b = colorsys.hsv_to_rgb(node.hue, 1, 0.5)

        print('''
            iso.add(
                Shape.Prism(Point(%f, %f, 0), %f, %f, %f),
                new Color(
                    parseInt(%f*255),
                    parseInt(%f*255),
                    parseInt(%f*255),
                    %f)
            );
        ''' % (x_offset, z_offset, width, depth, height, r, g, b, alpha))

    print('''

            // isomer doesn't support text, so DIY
            var ctx = document.getElementById('art').getContext('2d');
            ctx.font = '40pt sans-serif';
            ctx.fillStyle = 'black';

            var angle = 30;
            ctx.rotate(angle * Math.PI / 180);
            ctx.fillText('← Time', 1000, 800);

            angle = -60;
            ctx.rotate(angle * Math.PI / 180);
            ctx.fillText('← Columns →', 800, 2000);

            angle = -60;
            ctx.rotate(angle * Math.PI / 180);
            ctx.fillText('→ Rows', -600, 2390);
        });
        </script>

        <!--
        Note (Optional): To improve the look of your canvas on retina displays, declare the width and height of your
        canvas element as double how you want it to appear. Then style your canvas with CSS to include the original
        dimensions.
        -->
        <style>
            #art {
                width: 1200px;
                height: 800px;
            }
        </style>

        </head>
        <body>
        <canvas width="2400" height="1600" id="art"></canvas>
        </body>
        </html>
    ''')

    if sys.stdout.isatty():
        debug(graph)


if __name__ == '__main__':
    with open('example-plan.txt') as f:
        graph = parse(f.read())
        render(graph)
