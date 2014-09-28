import re
from itertools import chain
from operator import itemgetter
try:
    from itertools import izip_longest
except ImportError:
    from itertools import zip_longest as izip_longest

__version__ = "0.3.0"

MISSING = object()


class __base__(object):
    def __init__(self, *args, **kwargs):
        pass


def class_sealer(required, defaults, everything):
    class FieldsBase(__base__):
        def __init__(self, *args, **kwargs):
            required_ = required

            for name, value in dict(defaults, **kwargs).items():
                if name in required:
                    required_ = tuple(n for n in required_ if n != name)
                setattr(self, name, value)

            for pos, (name, value) in enumerate(izip_longest(required_, args, fillvalue=MISSING)):
                if value is MISSING:
                    raise TypeError("Required argument %r (pos %s) not found" % (name, pos))
                elif name is MISSING:
                    raise TypeError("%s takes at most %s arguments (%s given)" % (
                        type(self).__name__, len(required_), len(args)
                    ))
                else:
                    setattr(self, name, value)
            super(FieldsBase, self).__init__(*args, **kwargs)

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return tuple(getattr(self, a) for a in everything) == tuple(getattr(other, a) for a in everything)
            else:
                return NotImplemented

        def __ne__(self, other):
            result = self.__eq__(other)
            if result is NotImplemented:
                return NotImplemented
            else:
                return not result

        def __lt__(self, other):
            if isinstance(other, self.__class__):
                return tuple(getattr(self, a) for a in everything) < tuple(getattr(other, a) for a in everything)
            else:
                return NotImplemented

        def __le__(self, other):
            if isinstance(other, self.__class__):
                return tuple(getattr(self, a) for a in everything) <= tuple(getattr(other, a) for a in everything)
            else:
                return NotImplemented

        def __gt__(self, other):
            if isinstance(other, self.__class__):
                return tuple(getattr(self, a) for a in everything) > tuple(getattr(other, a) for a in everything)
            else:
                return NotImplemented

        def __ge__(self, other):
            if isinstance(other, self.__class__):
                return tuple(getattr(self, a) for a in everything) >= tuple(getattr(other, a) for a in everything)
            else:
                return NotImplemented

        def __hash__(self):
            return hash(tuple(getattr(self, a) for a in everything))

        def __repr__(self):
            return "{0}({1})".format(
                self.__class__.__name__,
                ", ".join(a + "=" + repr(getattr(self, a)) for a in everything)
            )
    return FieldsBase


def tuple_sealer(required, defaults, everything):
    if defaults:
        raise TypeError("tuple_sealer doesn't support default arguments")

    def __new__(cls, *args):
        return tuple.__new__(cls, args)

    def __getnewargs__(self):
        return tuple(self)

    def __repr__(self):
        return "{0}({1})".format(
            self.__class__.__name__,
            ", ".join(a + "=" + repr(getattr(self, a)) for a in everything)
        )

    return type("TupleBase", (tuple,), dict(
        [(name, property(itemgetter(i))) for i, name in enumerate(required)],
        __new__=__new__,
        __getnewargs__=__getnewargs__,
        __repr__=__repr__,
        __slots__=(),
    ))

class __type__(type):
    pass

def factory(field=None, required=(), defaults=(), sealer=class_sealer):
    klass = None
    full_required = required
    if field is not None:
        full_required += field,
    all_fields = sorted(chain(full_required, defaults))

    class Meta(__type__):
        """
        This class makes everything work. It a metaclass for the class that this factory returns. Each new chain
        rebuilds everything.

        Workflow::

            class T(factory().a.b.c) breaks down to:
                m1 = class Meta
                c1 = instance of Meta
                    m1.__new__ => c1 (factory branch, c1 is not in bases)
                factory() => c1

                c1.__getattr__ resolves to m1.__getattr__, c1 is instance of m1
                c1.__getattr__('a') => factory('a')
                    m2 = class Meta
                    c2 = instance of Meta
                        m2.__new__ => c2 (factory branch, c2 is not in bases)

                c2.__getattr__ resolves to m2.__getattr__, c2 is instance of m2
                c2.__getattr__('b') => factory('b', ('a',))
                    m3 = class Meta
                    c3 = instance of Meta
                        m3.__new__ => c3 (factory branch, c3 is not in bases)

                c3.__getattr__ resolves to m3.__getattr__, c3 is instance of m3
                c3.__getattr__('c') => factory('c', ('a', 'b'))
                    m4 = class Meta
                    c4 = instance of Meta
                        m4.__new__ => c4 (factory branch, c4 is not in bases)

                class T(c4) => type("T", (c4,), {})
                    m4.__new__ => T (sealing branch, c4 is found bases)
                        returns type("T", (FieldsBase,), {}) instead
        """
        concrete = None

        def __new__(mcs, name, bases, namespace):
            if klass in bases:
                if not all_fields:
                    raise TypeError("You're trying to use an empty Fields factory !")
                if defaults and field is not None:
                    raise TypeError("Can't add required fields after fields with defaults.")
                return type(name, tuple(
                    sealer(full_required, defaults, all_fields)
                    if k is klass else k for k in bases
                ), namespace)
            else:
                return type.__new__(mcs, name, bases, namespace)

        def __getattr__(cls, name):
            if name in required:
                raise TypeError("Field %r is already specified as required." % name)
            if name in defaults:
                raise TypeError("Field %r is already specified with a default value (%r)." % (
                    name, defaults[name]
                ))
            if name == field:
                raise TypeError("Field %r is already specified as required." % name)
            if defaults and field is not None:
                raise TypeError("Can't add required fields after fields with defaults.")
            return factory(name, full_required, defaults, sealer)

        def __getitem__(cls, default):
            if field is None:
                raise TypeError("Can't set default %r. There's no previous field." % default)

            new_defaults = {field: default}
            new_defaults.update(defaults)
            return factory(None, required, new_defaults, sealer)

        def __call__(self, *args, **kwargs):
            return (~self)(*args, **kwargs)

        def __invert__(self):
            if self.concrete is None:
                self.concrete = sealer(full_required, defaults, all_fields)
            return self.concrete

    klass = Meta(
        "Fields<%s>.%s" % (sealer.__name__, ".".join(all_fields))
        if all_fields
        else "Fields<%s>" % sealer.__name__,
        (object,),
        {}
    )
    return klass


class ValidationError(Exception):
    pass


def regex_validation_sealer(required, defaults, everything, RegexType=type(re.compile(""))):
    if required:
        raise TypeError("regex_validation_sealer doesn't support required arguments")

    klass = None
    kwarg_validators = dict(
        (key, val if isinstance(val, RegexType) else re.compile(val)) for key, val in defaults.items()
    )
    arg_validators = list(
        kwarg_validators[key] for key in everything
    )

    def __init__(self, *args, **kwargs):
        for pos, (value, validator) in enumerate(zip(args, arg_validators)):
            if not validator.match(value):
                raise ValidationError("Positional argument %s failed validation. %r doesn't match regex %r" % (
                    pos, value, validator.pattern
                ))
        for key, value in kwargs.items():
            if key in kwarg_validators:
                validator = kwarg_validators[key]
                if not validator.match(value):
                    raise ValidationError("Keyword argument %r failed validation. %r doesn't match regex %r" % (
                        key, value, validator.pattern
                    ))
        super(klass, self).__init__(*args, **kwargs)

    klass = type("RegexValidateBase", (__base__,), dict(
        __init__=__init__,
    ))
    return klass

Fields = factory()
Tuple = factory(sealer=tuple_sealer)
RegexValidate = factory(sealer=regex_validation_sealer)
