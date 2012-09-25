from django.contrib.auth.models import User
from geonode.layers.models import Layer
from geonode.maps.models import Map
from geonode.people.models import Contact
from itertools import cycle
from uuid import uuid4


# This is used to populate the database with the search fixture data. This is
# primarly used as a first step to generate the json data for the fixture using
# django's dumpdata


map_data = [
        ('lorem ipsum', 'common lorem ipsum'),
        ('ipsum lorem', 'common ipsum lorem'),
        ('lorem1 ipsum1', 'common abstract1'),
        ('ipsum foo', 'common bar lorem'),
        ('map one', 'common this is a unique thing'),
        ('quux', 'common double thing'),
        ('morx', 'common thing double'),
        ('titledupe something else ', 'whatever common'),
        ('something titledupe else ', 'bar common'),
        ]

user_data = [
        ('user1', 'pass', 'uniquefirst', 'foo'),
        ('user2', 'pass', 'foo', 'uniquelast'),
        ('unique_username', 'pass', 'foo', 'uniquelast'),
        ('jblaze', 'pass', 'johnny', 'blaze'),
        ('foo', 'pass', 'bar', 'baz'),
        ]

people_data = [
        ('this contains all my interesting profile information',),
        ('some other information goes here',),
        ]

layers = [
        ('layer1', 'abstract1', 'layer1', 'geonode:layer1', [-180, 180, -90, 90]),
        ('layer2', 'abstract2', 'layer2', 'geonode:layer2', [-180, 180, -90, 90]),
        ('uniquetitle', 'something here', 'mylayer', 'geonode:mylayer', [-180, 180, -90, 90]),
        ('blar', 'lorem ipsum', 'foo', 'geonode:foo', [-180, 180, -90, 90]),
        ('double it', 'whatever', 'whatever', 'geonode:whatever', [0, 1, 0, 1]),
        ('double time', 'else', 'fooey', 'geonode:fooey', [0, 5, 0, 5]),
        ('bar', 'uniqueabstract', 'quux', 'geonode:quux', [0, 10, 0, 10]),
        ('morx', 'lorem ipsum', 'fleem', 'geonode:fleem', [0, 50, 0, 50]),
        ]


def create_models():
    users = []
    for user_name, password, first_name, last_name in user_data:
        u = User.objects.create_user(user_name)
        u.first_name = first_name
        u.last_name = last_name
        u.save()
        users.append(u)

    people_data_generator = cycle(people_data)
    for u in users:
        profile = people_data_generator.next()[0]
        contact = Contact(profile=profile)
        contact.user = u
        contact.save()

    for title, abstract in map_data:
        m = Map(title=title,
                abstract=abstract,
                zoom=4,
                projection='EPSG:4326',
                center_x=42,
                center_y=-73,
                # searching probably doesn't care for map owners :P
                #owner=user
                )
        m.save()

    for layer_data, owner in zip(layers, cycle(users)):
        title, abstract, name, typename, (bbox_x0, bbox_x1, bbox_y0, bbox_y1) = layer_data
        l = Layer(title=title,
                  abstract=abstract,
                  name=name,
                  typename=typename,
                  bbox_x0=bbox_x0,
                  bbox_x1=bbox_x1,
                  bbox_y0=bbox_y0,
                  bbox_y1=bbox_y1,
                  uuid=str(uuid4()),
                  owner=owner,
                  )
        l.save()


if __name__ == '__main__':
    create_models()
