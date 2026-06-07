from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Q

from apps.online.models import OnlineCourse
from apps.training.models import TrainingContentItem, TrainingCourseRoleAssignment


@transaction.atomic
def enforce_single_primary_course_role(*, assignment: TrainingCourseRoleAssignment) -> None:
    if not assignment.is_primary:
        return

    (
        TrainingCourseRoleAssignment.objects.filter(
            course_id=assignment.course_id,
            role=assignment.role,
            is_primary=True,
        )
        .exclude(id=assignment.id)
        .update(is_primary=False)
    )


def build_training_governance_overview(*, course_id: int | None = None) -> dict[str, object]:
    content_queryset = TrainingContentItem.objects.all()
    role_queryset = TrainingCourseRoleAssignment.objects.all()
    course_queryset = OnlineCourse.objects.all()

    if course_id is not None:
        content_queryset = content_queryset.filter(course_id=course_id)
        role_queryset = role_queryset.filter(course_id=course_id)
        course_queryset = course_queryset.filter(id=course_id)

    courses_without_owner = course_queryset.exclude(
        training_role_assignments__role=TrainingCourseRoleAssignment.Role.OWNER
    ).count()
    owner_assignments = role_queryset.filter(role=TrainingCourseRoleAssignment.Role.OWNER).count()
    reviewer_assignments = role_queryset.filter(role=TrainingCourseRoleAssignment.Role.REVIEWER).count()
    instructor_assignments = role_queryset.filter(role=TrainingCourseRoleAssignment.Role.INSTRUCTOR).count()

    content_without_asset_class = content_queryset.annotate(asset_class_total=Count("asset_classes")).filter(
        asset_class_total=0
    )
    content_without_topic = content_queryset.annotate(topic_total=Count("topics")).filter(topic_total=0)
    internal_content_without_policy = content_queryset.annotate(policy_total=Count("audience_policies")).filter(
        access_scope=TrainingContentItem.AccessScope.ENTITLED,
        policy_total=0,
    )
    notebook_content_without_lab = content_queryset.filter(
        content_kind=TrainingContentItem.ContentKind.NOTEBOOK
    ).filter(Q(lab_profile__isnull=True) | Q(lab_profile__is_active=False) | Q(lab_profile__notebook_path=""))

    return {
        "courseId": course_id,
        "coursesWithoutOwner": courses_without_owner,
        "ownerAssignments": owner_assignments,
        "reviewerAssignments": reviewer_assignments,
        "instructorAssignments": instructor_assignments,
        "contentItems": content_queryset.count(),
        "notebookItems": content_queryset.filter(content_kind=TrainingContentItem.ContentKind.NOTEBOOK).count(),
        "contentWithoutAssetClass": content_without_asset_class.count(),
        "contentWithoutTopic": content_without_topic.count(),
        "contentWithoutOwner": content_queryset.filter(owner__isnull=True).count(),
        "internalContentWithoutAudiencePolicy": internal_content_without_policy.count(),
        "notebookContentWithoutLabProfile": notebook_content_without_lab.count(),
    }
