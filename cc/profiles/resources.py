from tastypie import fields
from tastypie.resources import ModelResource, ALL, ALL_WITH_RELATIONS

from models import InstagramInfo, InstagramPhoto


class InstagramResource(ModelResource):
    class Meta:
        queryset = InstagramInfo.objects.all()
        resource_name = 'instagram_license'
        filtering = {
            'instagram_username': ALL,
            'full_name': ALL,
            'license': ALL,
            'start_date': ALL,
            'end_date': ALL,
        }


class InstagramPhotoResource(ModelResource):
    license_info = fields.ForeignKey(InstagramResource, 'license_info',
        full=True)

    class Meta:
        queryset = InstagramPhoto.objects.all()
        resource_name = 'instagram_photo'
        filtering = {
            'license_info': ALL_WITH_RELATIONS,
            'caption': ALL,
            'created_time': ALL,
            'filter': ALL,
            'photo_id': ALL,
            'link': ALL,
            'tags': ALL,
            'location': ALL,
        }
