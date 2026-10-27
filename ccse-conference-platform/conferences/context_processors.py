from .permissions import can_edit, can_review


def roles(request):
    user = getattr(request, "user", None)
    if user is None:
        return {}
    return {"can_review": can_review(user), "can_edit": can_edit(user)}
