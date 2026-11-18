# Wagtail CMS

This project includes Wagtail with Django rendering. The existing users, Django admin remain available.

## First use

Start the project using the normal development setup and `tilt up`. The existing migration step creates a CMS home and a published example page once.

The migration init container automatically runs `initialize_cms` after `migrate`. It completes revisions, publication dates and search indexing for live starter pages that have no revision yet. Re-running it preserves edited pages and does not recreate deleted content. When running Django outside the provided Kubernetes setup, run `python manage.py initialize_cms` after the initial migrations.

Create an administrator using the existing backend shell:

```bash
make shell-backend
python manage.py createsuperuser
```

| Local URL | Purpose |
| --- | --- |
| `http://localhost:8000/cms/` | Wagtail editor login |
| `http://localhost:8000/content/` | CMS home |
| `http://localhost:8000/content/example/` | Published example |
| `http://localhost:8000/admin/` | Existing Django admin, subject to the configured admin URL |

In Wagtail, select **Pages → Content**, add a **Content page**, enter its title/body and publish. Nested pages receive routes automatically. Preview also works before the first publication and for unsaved edits. No seeding command, frontend route file or rebuild is needed for another page of the starter type. Re-running migrations preserves edits and does not recreate deleted example pages.



## Deployment and document access

Use the existing Terraform, sealed-secret and ArgoCD workflow. CMS addresses and storage values are generated from the normal project inputs:

| Environment | CMS pages | CMS admin/backend | Assets |
| --- | --- | --- | --- |
| Sandbox | `https://api.sandbox.wagtailspace02.scaf.sixfeetup.com/content/` | `https://api.sandbox.wagtailspace02.scaf.sixfeetup.com/cms/` | `https://sandbox.wagtailspace02.scaf.sixfeetup.com` |
| Production | `https://api.prod.wagtailspace02.scaf.sixfeetup.com/content/` | `https://api.prod.wagtailspace02.scaf.sixfeetup.com/cms/` | `https://prod.wagtailspace02.scaf.sixfeetup.com` |


CMS pages render directly on the backend. The public domain's CloudFront distribution serves assets from S3.


The sandbox/prod overlays select `wagtailspace02-{sandbox|prod}-static-storage`. `STORAGES` uses the existing S3 backends, private objects and CloudFront OAC. The deployment init container runs `collectstatic` before the backend starts. Existing sealed S3 credentials are available to both processes; IAM/SDK credentials remain supported outside that setup.

Only `static/`, `media/original_images/`, `media/images/` and Wagtail profile `media/avatar_images/` are public through CloudFront. Documents use Wagtail's `/documents/` serving view and collection permissions; direct document URLs are denied in development and through S3/CloudFront. Link documents using the editor's document chooser. Keep new private upload directories outside public CDN grants. To add another public media directory, update `public_asset_prefixes` in `terraform/modules/base/locals.tf`; both the bucket grant and CDN routing are derived from that list.

These generated defaults target new projects. Moving domains, existing files or Terraform state in an already deployed application requires a separate migration.

## Extend the starter

`cms/models.py` defines the abstract `CMSPage` and its concrete starter `ContentPage`, with title/slug, intro, rich text and an optional hero image. **Inherit new CMS page models from `CMSPage`, rather than directly from Wagtail's `Page`.** This shares the configured public URL origin and, in headless mode, preview/serving behavior. Update the parent's `subpage_types` and the new model's `parent_page_types` to allow the new type in the tree. Add fields/panels and run normal Django migrations for content-model changes. The initial migration deliberately has no dependency on the optional headless mixin.



The Django template is `cms/templates/cms/content_page.html`. Both modes use the same restricted rich text renderer; if you enable additional editor features, update its allowed tags/attributes and tests together. Run the existing backend checks after extending the contract.
