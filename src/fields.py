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


def _make_classname(all_fields, sealer):
    if all_fields:
        return "Fields<%s>.%s" % (sealer.__name__, ".".join(all_fields))
    else:
        return "Fields<%s>" % sealer.__name__


class Callable(object):
    def __init__(self, func):
        self.func = func

    @property
    def __name__(self):
        return self.func.__name__

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class Factory(type):
    """
    This class makes everything work. It a metaclass for the class that users are going to use. Each new chain
    rebuilds everything.
    """

    __required = ()
    __defaults = ()
    __all_fields = ()
    __last_field = None
    __full_required = ()
    __sealer = None
    __concrete = None

    def __getattr__(cls, name):
        if name in cls.__required:
            raise TypeError("Field %r is already specified as required." % name)
        if name in cls.__defaults:
            raise TypeError("Field %r is already specified with a default value (%r)." % (
                name, cls.__defaults[name]
            ))
        if name == cls.__last_field:
            raise TypeError("Field %r is already specified as required." % name)
        if cls.__defaults and cls.__last_field is not None:
            raise TypeError("Can't add required fields after fields with defaults.")

        return Factory(
            required=cls.__full_required,
            defaults=cls.__defaults,
            last_field=name,
            sealer=cls.__sealer,
        )

    def __getitem__(cls, default):
        if cls.__last_field is None:
            raise TypeError("Can't set default %r. There's no previous field." % default)

        new_defaults = {cls.__last_field: default}
        new_defaults.update(cls.__defaults)
        return Factory(
            required=cls.__required,
            defaults=new_defaults,
            sealer=cls.__sealer,
        )

    def __new__(mcs, name="__blank__", bases=(), namespace={}, last_field=None, required=(), defaults=(), sealer=Callable(class_sealer)):
        if not bases:
            assert isinstance(sealer, Callable)

            full_required = tuple(required)
            if last_field is not None:
                full_required += last_field,
            all_fields = sorted(chain(full_required, defaults))

            return type.__new__(
                Factory,
                "Fields<%s>.%s" % (sealer.__name__, ".".join(all_fields))
                if all_fields else "Fields<%s>" % sealer.__name__,
                bases,
                dict(
                    _Factory__required=required,
                    _Factory__defaults=defaults,
                    _Factory__all_fields=all_fields,
                    _Factory__last_field=last_field,
                    _Factory__full_required=full_required,
                    _Factory__sealer=sealer,
                )
            )
        else:
            return type(name, tuple(
                ~k if isinstance(k, Factory) else k for k in bases
            ), namespace)

    def __init__(cls, *args, **kwargs):
        pass

    def __call__(cls, *args, **kwargs):
        return (~cls)(*args, **kwargs)

    def __invert__(cls):
        if cls.__concrete is None:
            if not cls.__all_fields:
                raise TypeError("You're trying to use an empty Fields factory !")
            if cls.__defaults and cls.__last_field is not None:
                raise TypeError("Can't add required fields after fields with defaults.")

            cls.__concrete = cls.__sealer(cls.__full_required, cls.__defaults, cls.__all_fields)
        return cls.__concrete


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

Fields = Factory()
Tuple = Factory(sealer=Callable(tuple_sealer))
RegexValidate = Factory(sealer=Callable(regex_validation_sealer))
