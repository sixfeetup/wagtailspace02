import importlib
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.test.utils import isolate_apps
from django.urls import clear_url_caches
from PIL import Image as PillowImage
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.models import (
    PAGE_MODEL_CLASSES,
    Collection,
    CollectionViewRestriction,
    Page,
    Site,
)

from ..models import CMSPage, ContentPage
from ..rendering import render_body


@override_settings(
    CMS_PUBLIC_BASE_URL="https://site.example.test",
    CMS_BACKEND_BASE_URL="https://api.example.test",
)
class ContentTests(TestCase):
    def setUp(self):
        self.home = Site.objects.get(is_default_site=True).root_page.specific
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        storage = override_settings(MEDIA_ROOT=media.name)
        storage.enable()
        self.addCleanup(storage.disable)

    def page(self, slug, parent=None, publish=True):
        page = (parent or self.home).add_child(
            instance=ContentPage(
                title=slug, slug=slug, body="<p>Published content</p>", live=False
            )
        )
        revision = page.save_revision()
        if publish:
            revision.publish()
        page.refresh_from_db()
        return page

    def test_published_content_is_searchable(self):
        page = self.page("searchregression")
        results = ContentPage.objects.live().search("searchregression")
        self.assertEqual([result.pk for result in results], [page.pk])

    def test_initialize_cms_indexes_seed_pages_and_is_idempotent(self):
        example = self.home.get_children().specific().get(slug="example")
        call_command("initialize_cms", verbosity=0)
        example.refresh_from_db()
        self.assertIsNotNone(example.latest_revision_id)
        self.assertIsNotNone(example.live_revision_id)
        self.assertIsNotNone(example.first_published_at)
        self.assertEqual(list(ContentPage.objects.live().search("Example")), [example])
        revision_id, published_at = (
            example.latest_revision_id,
            example.first_published_at,
        )
        example.title = "User edit"
        example.save_revision().publish()
        edited_revision = example.latest_revision_id
        call_command("initialize_cms", verbosity=0)
        example.refresh_from_db()
        self.assertEqual(example.title, "User edit")
        self.assertEqual(example.latest_revision_id, edited_revision)
        self.assertNotEqual(example.latest_revision_id, revision_id)
        self.assertEqual(example.first_published_at, published_at)
        example.delete()
        call_command("initialize_cms", verbosity=0)
        self.assertFalse(ContentPage.objects.filter(slug="example").exists())

    def test_seeded_tree_and_canonical_origins(self):
        self.assertEqual(Page.find_problems(), ([], [], [], [], []))
        self.assertEqual(self.home.numchild, 1)
        self.assertEqual(self.home.full_url, "https://site.example.test/content/")
        with override_settings(CMS_PUBLIC_BASE_URL="https://api.prod.example.test"):
            self.assertEqual(
                self.home.full_url, "https://api.prod.example.test/content/"
            )

    @isolate_apps()
    def test_another_cms_model_inherits_public_url_policy(self):
        class AnotherPage(CMSPage):
            class Meta:
                app_label = "cms"

        # isolate_apps restores Django's registry; Wagtail also keeps its own list.
        self.addCleanup(PAGE_MODEL_CLASSES.remove, AnotherPage)
        page = AnotherPage(
            title="Another", slug="another", url_path=f"{self.home.url_path}another/"
        )
        self.assertEqual(page.full_url, "https://site.example.test/content/another/")

    def test_hero_description_and_title_fallback(self):
        output = BytesIO()
        PillowImage.new("RGB", (20, 10), "red").save(output, format="PNG")
        image = get_image_model().objects.create(
            title="IMG_2043",
            description="Red sunset over the sea",
            file=SimpleUploadedFile("hero.png", output.getvalue()),
        )
        page = self.page("hero-alt")
        page.hero_image = image
        page.save_revision().publish()
        for description, expected in [
            ("Red sunset over the sea", "Red sunset over the sea"),
            ("", "IMG_2043"),
        ]:
            image.description = description
            image.save()

            self.assertContains(
                self.client.get("/content/hero-alt/"), f'alt="{expected}"'
            )

    def test_rich_text_expansion_and_sanitizing(self):
        child = self.page("linked")
        html = render_body(
            f'<p><a linktype="page" id="{child.pk}">Page</a>'
            '<a href="/documents/12/file.pdf">Document</a>'
            '<img src="/media/images/example.jpg" alt="Example" width="20" height="10" onerror="alert(1)">'
            '<a href="javascript:alert(1)">Bad link</a><script>alert(1)</script></p>'
        )
        self.assertIn('/content/linked/"', html)
        self.assertIn("https://api.example.test/documents/12/file.pdf", html)
        self.assertIn("https://api.example.test/media/images/example.jpg", html)
        self.assertIn('alt="Example"', html)
        self.assertNotIn("onerror", html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("<script", html)

    def test_documents_are_served_only_through_permission_view(self):
        collection = Collection.get_first_root_node().add_child(
            name="Private documents"
        )
        CollectionViewRestriction.objects.create(
            collection=collection, restriction_type="login"
        )
        document = get_document_model().objects.create(
            title="Private document",
            collection=collection,
            file=SimpleUploadedFile("private.txt", b"private document bytes"),
        )
        self.assertNotEqual(self.client.get(document.url).status_code, 200)
        self.client.force_login(
            get_user_model().objects.create_user(username="reader", password="test")
        )
        response = self.client.get(document.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b"".join(response.streaming_content), b"private document bytes"
        )
        self.client.logout()
        public_file = default_storage.save(
            "images/public.txt", SimpleUploadedFile("public.txt", b"public media bytes")
        )
        document_paths = [
            document.file.name,
            "/" + document.file.name,
            "./" + document.file.name,
            "images/../" + document.file.name,
            document.file.name.replace("/", "//", 1),
            "images%2F..%2F" + document.file.name,
            document.file.name.replace("documents/", "DOCUMENTS/", 1),
        ]
        from config import urls

        try:
            for media_url in ["/media/", "/uploads/"]:
                with override_settings(DEBUG=True, MEDIA_URL=media_url):
                    importlib.reload(urls)
                    clear_url_caches()
                    for path in document_paths:
                        with self.subTest(media_url=media_url, path=path):
                            self.assertEqual(
                                self.client.get(media_url + path).status_code, 404
                            )
                    response = self.client.get(default_storage.url(public_file))
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        b"".join(response.streaming_content), b"public media bytes"
                    )
        finally:
            importlib.reload(urls)
            clear_url_caches()

    def test_native_rendering_and_preview(self):
        page = self.page("native")
        self.assertContains(self.client.get("/content/native/"), "Published content")
        page.body = "<p>Unsaved native preview</p>"
        response = page.serve_preview(self.client.request().wsgi_request, "")
        response.render()
        self.assertIn(b"Unsaved native preview", response.content)
        self.assertContains(self.client.get("/content/native/"), "Published content")
