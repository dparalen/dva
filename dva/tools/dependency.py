'''
a dependencies-handling module
'''

import logging
LOG = logging.getLogger(__name__)
WHITE='white'
GRAY='gray'
BLACK='black'


class Graph(object):
    '''The graph object'''
    def __init__(self, edges=set([]), vertices=set([])):
        self.vertices = vertices
        self.edges = edges

    def __repr__(self):
        return '%s(vertices=%r, edges=%r)' % (type(self).__name__, self.vertices, self.edges)

    def add_edge(self, from_vertex, to_vertex):
        '''add an edge--tuple registering the vertices'''
        self.vertices.add(from_vertex)
        self.vertices.add(to_vertex)
        self.edges.add((from_vertex, to_vertex))

    def add_vertex(self, vertex):
        ''' add a single vertex'''
        self.vertices |= set([vertex])

    def adjacent(self, other):
        '''get set of vertices adjacent to the vertex provided'''
        return set([adj_vertex for vertex, adj_vertex, in self.edges if vertex == other])


class Vertex(object):
    '''a vertex object'''
    def __init__(self, value=None, parent=None, color=WHITE, distance=-1):
        self.value = value
        self.color = color
        self.parent = parent
        self.distance = distance

    def __repr__(self):
            return '%r(value=%r, parent=%r, color=%r, distance=%r)' % (type(self).__name__, self.value, self.parent,
                    self.color, self.distance)

    def __cmp__(self, other):
        return cmp(self.value, other.value)

def bfs(G, root):
    '''
    the bfs algorithm modified to work in etages of the dependency tree built
    etages are being yielded for the caller to process during the graph traversal
    '''
    for vertex in G.vertices - set([root]):
        vertex.color = WHITE
        vertex.distance = -1
        vertex.parent = None

    root.color = GRAY
    root.distance = 0
    root.parent = None

    etage_0 = []
    etage_1 = []
    etage_0.append(root)
    while etage_0:
        yield etage_0
        while etage_0:
            vertex = etage_0.pop(0)
            for adj_vertex in G.adjacent(vertex):
                if adj_vertex.color is not WHITE:
                    continue
                adj_vertex.color = GRAY
                adj_vertex.distance = vertex.distance + 1
                adj_vertex.parent = vertex
                etage_1.append(adj_vertex)
            vertex.color = BLACK
        etage_0, etage_1 = etage_1, etage_0


