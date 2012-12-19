from datetime import datetime
import csv

from django.contrib.auth.models import User
from django.db.models import Max

from profiles.models import InstagramInfo


def run():
    need_renewal = InstagramInfo.objects.values('user').annotate(
        Max('end_date')).filter(end_date__lte=datetime.now())
    with open('users.csv', 'w') as csvfile:
        csvwriter = csv.writer(csvfile)
        for info in need_renewal:
            u = User.objects.get(id=info['user'])
            full_name = InstagramInfo.objects.filter(user=u)[0].full_name
            csvwriter.writerow([u.email, full_name])
    print "Wrote results to users.csv"
