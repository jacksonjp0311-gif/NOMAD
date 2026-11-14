def search(graph, start, path=None):
    """
    depth first search algorithm

    :param graph:
    :param start:
    :param path:
    :return:
    """
    # check if graph is empty or start vertex is none
    if start not in graph or graph[start] is None or graph[start] == []:
        return path

    _path = path + [start]
    for edge in graph[start]:
        if edge not in _path:
            _path = search(graph, edge, _path)
    return _path
