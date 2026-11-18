# :package: How to deploy

## Infrastructure provisioning

Terraform can be used to provision AWS resources for your project deployment.
Read [terraform/README.md](/terraform/README.md) for more information and steps for provisioning resources.

Sandbox uses `sandbox.wagtailspace02.scaf.sixfeetup.com` for the public site/assets and
`api.sandbox.wagtailspace02.scaf.sixfeetup.com` for Django. Production uses
`prod.wagtailspace02.scaf.sixfeetup.com` and `api.prod.wagtailspace02.scaf.sixfeetup.com` respectively.

The public domain serves assets; application pages remain on the Django host.


Deployment collects static files into the environment's private S3 bucket before
starting Django. Bucket names and asset domains are generated in the overlays;
provide the normal sealed S3 credentials through the existing bootstrap workflow.
Both the backend and static-collection init container use those credentials.

See [Wagtail CMS](wagtail.md) for CMS URLs, document permissions and content extension points.


## Application deployment

Use ArgoCD and Kubernetes to automate the deployment of your application to your infrastructure. ArgoCD monitors changes within your repository, promptly applying the relevant Kubernetes manifests. Read [bootstrap-cluster/README.md](/bootstrap-cluster/README.md) for more details.
