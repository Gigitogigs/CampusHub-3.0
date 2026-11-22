from .models import User

def users_visible_to(actor):
    """Return undeleted users visible to the actor within their tenant scope.
       If actor is platform staff, return all undeleted users. 
       If actor is a university admin or student, return undeleted users within the same university.
       If actor has no university, return an empty queryset.
    """
    qs = User.objects.filter(deleted_at__isnull=True)
    if actor.platform_staff:
        return qs
    if actor.university_id is None:
        return qs.none()          # see the warning below
    return qs.filter(university_id=actor.university_id)
