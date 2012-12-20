from datetime import datetime, timedelta
import json
from copy import copy

from django.views.generic.edit import UpdateView
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import logout
from django.core.cache import cache
from django import forms
from django.utils.timezone import utc

from external_apis import instagram

from models import InstagramInfo, InstagramPhoto
from utils import get_access_token, from_unix_time, to_unix_time


class LicenseForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    old_photos = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = InstagramInfo
        fields = ('license', 'full_name')

    def clean_email(self, **kwargs):
        email = self.cleaned_data['email']
        self.instance.user.email = email
        self.instance.user.save()

    def clean_license(self, **kwargs):
        license = self.cleaned_data['license']
        # If they already had a license type set and then they go in and
        # change it then we should create an entirely new InstgramInfo
        # instance to represent this.  Otherwise we'll lose information
        # about what the old license was and when it applied.
        already_exists = self.instance.start_date
        if already_exists and self.instance.license != license:
            old_instance = self.instance
            # Make a new instance on save
            self.instance = copy(self.instance)
            self.instance.id = None
            self.instance.pk = None
            # Make the new instance's start date be right now
            self.instance.start_date = datetime.now().replace(tzinfo=utc)
            old_instance.end_date = self.instance.start_date

            old_instance.save()
        return license

    def clean_old_photos(self, **kwargs):
        if self.cleaned_data['old_photos']:
            # Set this to before Instagram's creation
            # which was Oct, 2010
            self.instance.start_date = datetime(2010, 9, 1, 0, 0)


class InstagramLicenseUpdate(UpdateView):
    model = InstagramInfo
    form_class = LicenseForm

    def get_object(self, **kwargs):
        user = self.request.user
        # Didn't yet complete form
        if InstagramInfo.objects.filter(user=user, end_date=None):
            return InstagramInfo.objects.filter(user=user, end_date=None)[0]
        # Get most recent info they've entered and use that
        return InstagramInfo.objects.filter(
            user=self.request.user).order_by('-end_date')[0]

    def form_valid(self, form):
        if form.data.get('stop'):
            form.instance.end_date = datetime.now().replace(tzinfo=utc)
            form.save()
            logout(self.request)
            return HttpResponseRedirect('/instagram-stopped/')

        if not form.instance.start_date:
            form.instance.start_date = datetime.now()
        # Good for 3 months
        form.instance.end_date = datetime.now() + timedelta(weeks=12)

        form.save()
        return HttpResponseRedirect('/instagram-done/')

    def get_context_data(self, **kwargs):
        context = super(InstagramLicenseUpdate, self).get_context_data(
            **kwargs)
        if context['form'].instance.user.email:
            context['form'].initial['email'] = context['form'].instance.user.email
        context['end_date'] = (datetime.now().replace(tzinfo=utc) +
            timedelta(weeks=12))
        context['existing_license'] = self.object.end_date
        return context


def index(request):
    context = {
        'info_objs': InstagramInfo.objects.all().exclude(end_date=None).order_by('-end_date')[:50],
        'num_users': len(InstagramInfo.objects.values('user').distinct()),
        'recent_photos': get_recent_photos(limit=50),
    }
    return render_to_response('index.html', context)


def save_image_info(api_result, info):
    if InstagramPhoto.objects.filter(photo_id=api_result.get('id')):
        # Photo already exists, let's skip it
        # TODO: In the future perhaps we can allow re-licensing of
        # existing photos.
        return
    caption = api_result.get('caption')
    if caption:
        caption = caption.get('text', None)
    photo = InstagramPhoto(
        license_info=info,
        caption=caption,
        created_time=from_unix_time(int(api_result.get('created_time'))),
        filter=api_result.get('filter'),
        photo_id=api_result.get('id'),
        image_low_resolution=api_result.get('images', {}
            )['low_resolution']['url'],
        image_standard_resolution=api_result.get('images', {}
            )['standard_resolution']['url'],
        image_thumbnail=api_result.get('images', {}
            )['thumbnail']['url'],
        link=api_result.get('link'),
        tags=json.dumps(api_result.get('tags')),
        location=json.dumps(api_result.get('location')),
    )
    photo.save()


MAX_API_PER_GENERATION = 50


def generate_image_info(username=None, limit=None):
    d = {}
    if username:
        d = {'instagram_username': username}
    # last_used_in_api helps us limit the # of API calls
    infos = InstagramInfo.objects.filter(**d).exclude(end_date=None).\
        order_by('last_used_in_api')[:MAX_API_PER_GENERATION]

    for info in infos:
        last_saved = info.start_date
        if InstagramPhoto.objects.filter(license_info=info):
            latest_saved_photo = InstagramPhoto.objects.filter(
                license_info=info).order_by('-created_time')[0]
            last_saved = latest_saved_photo.created_time

        recent = cache.get('api_rc_%s' % info.instagram_id)
        if recent is None:
            # Get the most recent since we last cached from the API
            try:
               recent_resp = instagram.api.users(info.instagram_id).media.\
                   recent.get(
                       access_token=get_access_token(info.user),
                       max_timestamp=to_unix_time(info.end_date),
                       min_timestamp=to_unix_time(last_saved))
            except:
                return
            recent = recent_resp['data']
            # One hour cache per-user
            cache.set('api_rc_%s' % info.instagram_id, recent, 60 * 60)

        for item in recent:
            # The API returns items even if they're before min_timestamp
            # sometimes, so we have to check by hand here.
            created_time = from_unix_time(int(item['created_time']))
            if (created_time < info.end_date and
                created_time > info.start_date and created_time > last_saved):
                save_image_info(item, info)

        info.last_used_in_api = datetime.now().replace(tzinfo=utc)
        info.save()


def get_recent_photos(username=None, limit=None):
    generate_image_info(username, limit)
    if username:
        taken_by_user = InstagramInfo.objects.filter(
            instagram_username=username).exclude(end_date=None)
        return InstagramPhoto.objects.filter(
            license_info__in=taken_by_user).order_by('-created_time')[:limit]
    return InstagramPhoto.objects.all().order_by('-created_time')[:limit]


def instagram_list(request, username=None):
    if InstagramInfo.objects.filter(instagram_username=username):
        info = InstagramInfo.objects.filter(instagram_username=username)[0]

    return render_to_response('photo_list.html', {
        'photos': get_recent_photos(username=username),
        'info': info,
    })


def photo_page(request, username=None, photo_id=None):
    photo = InstagramPhoto.objects.get(id=photo_id)

    return render_to_response('photo_page.html', {
        'photo': photo,
    })
