from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.db.models import Q

from geonode.maps.models import *
from geonode.maps.views import _metadata_search
from geonode.maps.views import _split_query

import re

_exclude_patterns = []
'''Settings API - allow regular expressions to filter our layer name results'''
if hasattr(settings,'SIMPLE_SEARCH_EXCLUSIONS'):
    _exclude_patterns = [ re.compile(e) for e in settings.SIMPLE_SEARCH_EXCLUSIONS ]
    
def _filter_results(l):
    '''If the layer name doesn't match any of the patterns, it shows in the results'''
    return not any(p.search(l['name']) for p in _exclude_patterns)

class Normalizer:
    '''Base class to allow lazy normalization of Map and Layer attributes.
    
    The two fields we support sorting on are title and last_modified so these
    must be computed up front.
    '''
    def __init__(self,o,data = None):
        self.o = o
        self.data = data
        self.dict = None
        self.title = o.title
        self.last_modified = self.last_modified(o)
    def last_modified(self,o):
        abstract
    def as_dict(self):
        if self.dict is None:
            self.dict = self.populate(self.data)
            self.dict['iid'] = self.iid
        return self.dict
    
class MapNormalizer(Normalizer):
    def last_modified(self,map):
        return map.last_modified.isoformat()
    def populate(self, dict):
        map = self.o
        try:
            owner_name = Contact.objects.get(user=map.owner).name
        except:
            owner_name = map.owner.first_name + " " + map.owner.last_name
        thumb = Thumbnail.objects.get_thumbnail(map)
        # resolve any local layers and their keywords
        local_kw = [ l.keywords.split(' ') for l in map.local_layers if l.keywords]
        keywords = local_kw and list(set( reduce(lambda a,b: a+b, local_kw))) or []
        return {
            'id' : map.id,
            'title' : map.title,
            'abstract' : map.abstract,
            'topic' : '', # @todo
            'detail' : reverse('geonode.maps.views.map_controller', args=(map.id,)),
            'owner' : owner_name,
            'owner_detail' : reverse('profiles.views.profile_detail', args=(map.owner.username,)),
            'last_modified' : map.last_modified.isoformat(),
            '_type' : 'map',
            '_display_type' : 'Map',
            'thumb' : thumb and thumb.get_thumbnail_url() or None,
            'keywords' : keywords
        }
        
class LayerNormalizer(Normalizer):
    def last_modified(self,layer):
        return layer.date.isoformat()
    def populate(self, doc):
        layer = self.o
        thumb = Thumbnail.objects.get_thumbnail(layer)
        doc['owner'] = layer.metadata_author.name
        doc['thumb'] = thumb and thumb.get_thumbnail_url() or None
        doc['last_modified'] = layer.date.isoformat()
        doc['id'] = layer.id
        doc['_type'] = 'layer'
        doc['topic'] = layer.topic_category
        doc['storeType'] = layer.storeType
        doc['_display_type'] = layer.display_type
        owner = layer.owner
        if owner:
            doc['owner_detail'] = reverse('profiles.views.profile_detail', args=(layer.owner.username,))
        return doc
        
def _get_map_results(results, query, kw):
    map_query = Map.objects.all()

    if query:
        keywords = _split_query(query)
        for keyword in keywords:
            map_query = map_query.filter(
                  Q(title__icontains=keyword)
                | Q(abstract__icontains=keyword))

    results.extend( [MapNormalizer(m) for m in map_query ] )

        
def _get_layer_results(results, query, kw):
    
    # cache geonetwork results
    cache_key = query and 'search_results_%s' % query or 'search_results'
    layer_results = cache.get(cache_key)
    if not layer_results:
        layer_results = _metadata_search(query, 0, 1000)['rows']
        layer_results = filter(_filter_results, layer_results)
        # @todo search cache timeout in settings?
        cache.set(cache_key, layer_results, timeout=300)
    
    #build our Layer query, first by uuids
    Q = Layer.objects.filter(uuid__in=[ doc['uuid'] for doc in layer_results ])
    
    bytype = kw.get('bytype', None)
    if bytype and bytype != 'layer':
        Q = Q.filter(storeType = bytype)
        
    bytopic = kw.get('bytopic', None)
    if bytopic:
        Q = Q.filter(topic_category = bytopic)
        
    layers = dict([ (l.uuid,l) for l in Q])
    
    for doc in layer_results:
        layer = layers.get(doc['uuid'],None)
        if layer is None: continue #@todo - remote layer (how to get last_modified?)
        results.append(LayerNormalizer(layer,doc))

def combined_search_results(query, kw):
    results = []
    
    if 'bytype' not in kw or kw['bytype'] == u'map':
        _get_map_results(results, query, kw)
        
    if 'bytype' not in kw or kw['bytype'] != u'map':
        _get_layer_results(results, query, kw)
        
    return results