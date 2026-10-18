from django.db import migrations, models


def protect_imported_identity_on_reverse(apps, schema_editor):
    link = apps.get_model("db", "IssueLink")
    if link._base_manager.using(schema_editor.connection.alias).filter(external_source__isnull=False).exists():
        raise RuntimeError(
            "Cannot remove imported link identities; restore a compatible backup or retain this schema."
        )


class Migration(migrations.Migration):
    dependencies = [("db", "0122_alter_draftissue_assignees_alter_issue_assignees_and_more")]

    operations = [
        migrations.AddField(
            model_name="issuelink", name="external_source",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="issuelink", name="external_id",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddConstraint(
            model_name="issuelink",
            constraint=models.UniqueConstraint(
                fields=["workspace", "external_source", "external_id"],
                name="issue_link_source_identity_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="issuelink",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(external_source__isnull=True, external_id__isnull=True)
                    | (
                        models.Q(external_source__isnull=False, external_id__isnull=False)
                        & ~models.Q(external_source="") & ~models.Q(external_id="")
                    )
                ),
                name="issue_link_source_identity_complete",
            ),
        ),
        migrations.RunSQL(
            sql="""
                CREATE FUNCTION plane_issue_link_identity_immutable() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    IF OLD.external_source IS NOT NULL AND (
                        NEW.external_source IS DISTINCT FROM OLD.external_source
                        OR NEW.external_id IS DISTINCT FROM OLD.external_id
                        OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
                    ) THEN
                        RAISE EXCEPTION 'Imported link identity cannot be changed'
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END;
                $$;
                CREATE TRIGGER issue_link_identity_immutable
                    BEFORE UPDATE OF external_source, external_id, workspace_id ON issue_links
                    FOR EACH ROW EXECUTE FUNCTION plane_issue_link_identity_immutable();
            """,
            reverse_sql="""
                DROP TRIGGER issue_link_identity_immutable ON issue_links;
                DROP FUNCTION plane_issue_link_identity_immutable();
            """,
        ),
        # Reversal checks before dropping any fields, constraints or triggers.
        migrations.RunPython(migrations.RunPython.noop, protect_imported_identity_on_reverse),
    ]
