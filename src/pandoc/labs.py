"""
Design
================================================================================

TODO: first step: forget about lazyness and performance.

Fundamental object: Query.

  - Query defined independently of the root(s) it will be applied to.

  - Query is a callable ? Once defined, applied with `query(doc)` for
    example ? Or stuff = query(doc) is the aim is some extraction ?
    Or for item in query(doc): do_stuff_with(item). Root(s?) can be
    a Pandoc item or a list or tuple of stuff, etc.
    
    Could also envision query methods directly on Pandoc Elements ...
    dunno, have to think of it. Would be convenient (shorter code), 
    but messy (Elements are not "algebraic datatypes" anymore).

  - Query construction uses chaining (fluent) interface : chaining of
    transforms, chaining of filters, etc.

  - Query definition is lazy, does not compute anything: just abstract
    description of what we intend to do.

  - Query applied to a root : by default all items (in doc order)

  - Query filters: may reduce the list of items. Chaining is an "AND" thus
    a single-filter should be likely "OR"-based. E.g.
    query.filter((Para, Plain)) means keep Para OR Plain.
    Possible filters : filter(types), filter(predicate), has_attr(...),
    id_is(id=...), etc. Need to have stuff to match the existence of a feature
    has well as its value (ex: has id vs id is "main"). Also, class matching,
    etc. Essentially, many syntaxic sugar on top of "filter(predicate)".
    May need a meta stuff: .either(pred1, pred2, ...) ? Have a look at
    shader graph to see how stuff is forked/join with such interfaces.

  - Navigation: .parent, .children, .next_sibling, get_item[i]. Extract a 
    general "navigate" function such that all that stuff is merely syntaxic
    sugar ?

  - Mutation: .remove(), .replace_with(stuff), etc. Probably complex to get it
    right here. All this stuff should be TERMINAL : if any, nothing can be
    chained after that. Also: set attributes, ids, etc.
    Again, can we come up with a single, root, general mutation operation ?
    Or is it too complex here?
    Apply mutation in reverse order by default?

  - Iteration ? Query as a container "removes" path info by default so that
    we can deal with a list of "document items", make comprehensions, etc.
"""

# 🚧: Document that multiple arguments + `not_` + chaining calls allows to
#     express arbitrary boolean logic in [conjunctive normal form][CNF].
#
#     [CNF]: https://en.wikipedia.org/wiki/Conjunctive_normal_form

# Python Standard Library
pass

# Third-Party Libraries
pass

# Pandoc
import pandoc


# Logic
# ------------------------------------------------------------------------------
def to_function(predicate):
    if isinstance(predicate, type):
        return lambda elt: isinstance(elt, predicate)
    elif callable(predicate):
        return predicate
    else:
        error = "predicate should be a type or a function"
        error += f", not {predicate!r}"
        raise TypeError(error)

def not_(predicate):
    return lambda *args, **kwargs: not predicate(*args, **kwargs)

# Queries & Results
# ------------------------------------------------------------------------------
def query(root):
    return Query([(root, [])])

def _getitem(sequence, indices):
    if not hasattr(sequence, "__getitem__") or isinstance(sequence, str):
        raise TypeError()
    if isinstance(sequence, dict):
        sequence = list(sequence.items())
    return sequence[indices]

class Query: 
    def __init__(self, *results):
        self._elts = []
        for result in results:
            if isinstance(result, Query):
                self._elts.extend(result._elts) # Mmmm ownership issues
            else: # "raw results": list of (elt, path)
                self._elts.extend(result)

    # ℹ️ The call `find(object)` is public and equivalent to `_iter()`.
    def _iter(self):
        results = []
        for root, root_path in self._elts:
            for elt, path in pandoc.iter(root, path=True):
                path = root_path + path
                results.append((elt, path))
        return Query(results)

    # 🚧 Think of a rename given that we now can expose this as a property
    #    (optionally restricted with a call). We can keep find and the
    #    "functionally flavor", but a more content-oriented alias would
    #    be nice (descendants? But we also return the node itself. 
    #    Subtree? Tree? Contents?)
    def find(self, *predicates):
        return self._iter().filter(*predicates)
    
    def filter(self, *predicates):
        predicates = [to_function(predicate) for predicate in predicates]
        results = []
        for elt, path in self._elts:
            for predicate in predicates:
                if predicate(elt):
                    results.append((elt, path))
                    break
        return Query(results)

    # ✨ This is sweet! The intended usage is `.property(test)`, 
    #    which emulates the jquery API where functions can restrict the match. 
    #    It also allows us call the "functions" without parentheses 
    #    when no restriction is needed.
    def __call__(self, *predicates):
        return self.filter(*predicates)

    def get_children(self):
        # 🚧 TODO: use _getitem
        results = []
        for elt, path in self._elts:
            if isinstance(elt, dict):
                for i, child in enumerate(elt.items()):
                    child_path = path.copy() + [(elt, i)]
                    results.append((child, child_path))
            elif hasattr(elt, "__iter__") and not isinstance(elt, str):
                for i, child in enumerate(elt):
                    child_path = path.copy() + [(elt, i)]
                    results.append((child, child_path))
        return Query(results)

    children = property(get_children)

    def get_child(self, i):
        results = []
        for elt, elt_path in self._elts:
            children = []
            if isinstance(elt, pandoc.types.String) or not hasattr(elt, "__iter__"):
                children = []
            elif isinstance(elt, dict):
                children = list(elt.items())
            else:
                children = elt[:]

            if isinstance(i, int):
                try:
                    child = children[i]
                    results.append((child, elt_path.copy() + [(elt, i)]))
                except IndexError:
                    pass
            elif isinstance(i, slice):
                indices = range(len(children))[i]
                for index in indices:
                    child = children[index]
                    results.append((child, elt_path.copy() + [(elt, index)]))
        return Query(results)

    def get_parent(self):
        results = []
        for _, path in self._elts:
            if path != []:
                results.append((path[-1][0], path[:-1]))
        return Query(results)

    parent = property(get_parent)

    def get_next(self):
        indices = [path[-1][1] for elt, path in self._elts if path != []]
        results = []
        for (parent_elt, parent_path), index in zip(self.parent._elts, indices):
            try: # 🚧 TODO: adaptation of [] for dicts and strings (use _getitem).             
                next_element = parent_elt[index + 1]
                results.append((next_element, parent_path.copy() + [(parent_elt, index+1)]))
            except IndexError:
                pass
        return Query(results)

    next = property(get_next)

    def get_prev(self):
        indices = [path[-1][1] for elt, path in self._elts if path != []]
        results = []
        for (parent_elt, parent_path), index in zip(self.parent._elts, indices):
            if index > 0:
                try: # 🚧 TODO: adaptation of [] for dicts and strings (& factor out).
                    next_element = parent_elt[index - 1]
                    results.append((next_element, parent_path.copy() + [(parent_elt, index-1)]))
                except IndexError:
                    pass
        return Query(results)

    prev = property(get_prev)

    # Query container (hide path info)
    # --------------------------------------------------------------------------
    def __len__(self):
        return len(self._elts)

    def __getitem__(self, i):
        return Query([self._elts[i]])

    def __iter__(self):
        return (elt for elt, _ in self._elts)

    def __repr__(self):
        return "\n".join("- " + repr(elt) for elt, path in self._elts)