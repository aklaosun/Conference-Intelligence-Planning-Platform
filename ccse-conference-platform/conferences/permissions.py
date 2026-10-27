from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

REVIEWERS = "Reviewers"
EDITORS = "Editors"


def in_group(user, *names):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=names).exists()


def can_review(user):
    return in_group(user, REVIEWERS)


def can_edit(user):
    return in_group(user, EDITORS, REVIEWERS)


def _require(check):
    def decorator(view):
        def wrapped(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        wrapped.__name__ = view.__name__
        return user_passes_test(lambda u: u.is_authenticated)(wrapped)
    return decorator


reviewer_required = _require(can_review)
editor_required = _require(can_edit)
