from django.conf import settings
from django.contrib import admin
from guardian.admin import GuardedModelAdmin


# Import the form for assigning validation tasks
from documents.forms import AssignValidationTaskForm  # Import the new form
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages


from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import PaperlessTask
from documents.models import SavedView
from documents.models import SavedViewFilterRule
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.models import ValidationTask

if settings.AUDIT_LOG_ENABLED:
    from auditlog.admin import LogEntryAdmin
    from auditlog.models import LogEntry


class CorrespondentAdmin(GuardedModelAdmin):
    list_display = ("name", "match", "matching_algorithm")
    list_filter = ("matching_algorithm",)
    list_editable = ("match", "matching_algorithm")


class TagAdmin(GuardedModelAdmin):
    list_display = ("name", "color", "match", "matching_algorithm")
    list_filter = ("matching_algorithm",)
    list_editable = ("color", "match", "matching_algorithm")
    search_fields = ("color", "name")


class DocumentTypeAdmin(GuardedModelAdmin):
    list_display = ("name", "match", "matching_algorithm")
    list_filter = ("matching_algorithm",)
    list_editable = ("match", "matching_algorithm")


class DocumentAdmin(GuardedModelAdmin):
    search_fields = ("correspondent__name", "title", "content", "tags__name")
    readonly_fields = (
        "added",
        "modified",
        "mime_type",
        "storage_type",
        "filename",
        "checksum",
        "archive_filename",
        "archive_checksum",
        "original_filename",
        "deleted_at",
    )

    list_display_links = ("title",)

    list_display = ("id", "title", "mime_type", "filename", "archive_filename")

    list_filter = (
        ("mime_type"),
        ("archive_serial_number", admin.EmptyFieldListFilter),
        ("archive_filename", admin.EmptyFieldListFilter),
    )

    actions = ['assign_validation_task']  # Add this if not present

    filter_horizontal = ("tags",)

    ordering = ["-id"]

    date_hierarchy = "created"

    def has_add_permission(self, request):
        return False

    def created_(self, obj):
        return obj.created.date().strftime("%Y-%m-%d")

    created_.short_description = "Created"

    def get_queryset(self, request):  # pragma: no cover
        """
        Include trashed documents
        """
        return Document.global_objects.all()

    def delete_queryset(self, request, queryset):
        from documents import index

        with index.open_index_writer() as writer:
            for o in queryset:
                index.remove_document(writer, o)

        super().delete_queryset(request, queryset)

    def delete_model(self, request, obj):
        from documents import index

        index.remove_document_from_index(obj)
        super().delete_model(request, obj)

    def save_model(self, request, obj, form, change):
        from documents import index

        index.add_or_update_document(obj)
        super().save_model(request, obj, form, change)

    def assign_validation_task(self, request, queryset):
        if 'apply' in request.POST:
            form = AssignValidationTaskForm(request.POST)
            if form.is_valid():
                assigned_to = form.cleaned_data['assigned_to']
                tag = form.cleaned_data['tag']
                note = form.cleaned_data['note']
                selected_ids = request.POST.getlist('_selected_action')

                # Create the task
                task = ValidationTask.objects.create(
                    assigned_to=assigned_to,
                    created_by=request.user,
                    tag=tag,
                    note=note,
                    due_date=tag.due_date if tag else None  # Set from tag
                )
                # Link selected documents
                documents = Document.objects.filter(pk__in=selected_ids)
                task.documents.set(documents)
                # Optional: Assign tag to each document
                for doc in documents:
                    doc.tags.add(tag)
                    doc.save()

                messages.success(request, f"Validation task created for {documents.count()} documents.")
                return HttpResponseRedirect('.')
        else:
            initial = {
                '_selected_action': request.POST.getlist('_selected_action'),
                'assigned_to': request.user,  # Default to current user
            }
            form = AssignValidationTaskForm(initial=initial)

        context = {
            'form': form,
            'documents': queryset,
            'title': 'Assign Validation Task',
        }
        return render(request, 'admin/assign_validation_task.html', context)

    assign_validation_task.short_description = "Assign validation task to selected documents"

# Optional: Inline for viewing tasks in Document admin (shows linked tasks)
class ValidationTaskInline(admin.TabularInline):
    model = ValidationTask.documents.through  # For M2M inline
    extra = 0
    verbose_name = "Linked Validation Task"
    verbose_name_plural = "Linked Validation Tasks"


class RuleInline(admin.TabularInline):
    model = SavedViewFilterRule


class SavedViewAdmin(GuardedModelAdmin):
    list_display = ("name", "owner")

    inlines = [RuleInline]

    def get_queryset(self, request):  # pragma: no cover
        return super().get_queryset(request).select_related("owner")


class StoragePathInline(admin.TabularInline):
    model = StoragePath


class StoragePathAdmin(GuardedModelAdmin):
    list_display = ("name", "path", "match", "matching_algorithm")
    list_filter = ("path", "matching_algorithm")
    list_editable = ("path", "match", "matching_algorithm")


class TaskAdmin(admin.ModelAdmin):
    list_display = ("task_id", "task_file_name", "task_name", "date_done", "status")
    list_filter = ("status", "date_done", "task_name")
    search_fields = ("task_name", "task_id", "status", "task_file_name")
    readonly_fields = (
        "task_id",
        "task_file_name",
        "task_name",
        "status",
        "date_created",
        "date_started",
        "date_done",
        "result",
    )


class NotesAdmin(GuardedModelAdmin):
    list_display = ("user", "created", "note", "document")
    list_filter = ("created", "user")
    list_display_links = ("created",)
    raw_id_fields = ("document",)
    search_fields = ("document__title",)

    def get_queryset(self, request):  # pragma: no cover
        return (
            super()
            .get_queryset(request)
            .select_related("user", "document__correspondent")
        )


class ShareLinksAdmin(GuardedModelAdmin):
    list_display = ("created", "expiration", "document")
    list_filter = ("created", "expiration", "owner")
    list_display_links = ("created",)
    raw_id_fields = ("document",)

    def get_queryset(self, request):  # pragma: no cover
        return super().get_queryset(request).select_related("document__correspondent")


class CustomFieldsAdmin(GuardedModelAdmin):
    fields = ("name", "created", "data_type")
    readonly_fields = ("created", "data_type")
    list_display = ("name", "created", "data_type")
    list_filter = ("created", "data_type")


class CustomFieldInstancesAdmin(GuardedModelAdmin):
    fields = ("field", "document", "created", "value")
    readonly_fields = ("field", "document", "created", "value")
    list_display = ("field", "document", "value", "created")
    search_fields = ("document__title",)
    list_filter = ("created", "field")

    def get_queryset(self, request):  # pragma: no cover
        return (
            super()
            .get_queryset(request)
            .select_related("field", "document__correspondent")
        )


admin.site.register(Correspondent, CorrespondentAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(DocumentType, DocumentTypeAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(SavedView, SavedViewAdmin)
admin.site.register(StoragePath, StoragePathAdmin)
admin.site.register(PaperlessTask, TaskAdmin)
admin.site.register(Note, NotesAdmin)
admin.site.register(ShareLink, ShareLinksAdmin)
admin.site.register(CustomField, CustomFieldsAdmin)
admin.site.register(CustomFieldInstance, CustomFieldInstancesAdmin)

if settings.AUDIT_LOG_ENABLED:

    class LogEntryAUDIT(LogEntryAdmin):
        def has_delete_permission(self, request, obj=None):
            return False

    admin.site.unregister(LogEntry)
    admin.site.register(LogEntry, LogEntryAUDIT)

@admin.register(ValidationTask)
class ValidationTaskAdmin(admin.ModelAdmin):
    list_display = ['tag', 'assigned_to', 'due_date', 'status', 'created_by', 'created_at', 'get_documents_count']
    list_filter = ['status', 'due_date', 'assigned_to', 'created_by', 'tag']
    search_fields = ['note', 'assigned_to__username', 'tag__name']
    filter_horizontal = ['documents']  # For easy M2M selection in admin
    raw_id_fields = ['assigned_to', 'created_by', 'tag']
    date_hierarchy = 'created_at'

    def get_documents_count(self, obj):
        return obj.documents.count()
    get_documents_count.short_description = 'Documents'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if request.user.groups.filter(name='Staff').exists():
                return qs.filter(created_by=request.user) | qs.filter(assigned_to=request.user)
            else:
                return qs.none()
        return qs

    def has_add_permission(self, request):
        if request.user.is_superuser or request.user.groups.filter(name='Staff').exists():
            return True
        return False
