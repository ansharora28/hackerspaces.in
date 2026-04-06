document.addEventListener('DOMContentLoaded', () => {
  const $ = s => document.querySelector(s), $$ = s => document.querySelectorAll(s);
  const items = $$('[data-space]');
  if (!items.length) {
    return;
  }

  const elSearch = $('#search'), elCount = $('#count');
  const elChk = $$('[data-filter]');
  const elMap = $('[data-map]'), elShowMap = $('#show-map'), elToggles = $$('[data-toggle]');
  const isMobile = matchMedia('(max-width: 900px)').matches;
  let map, isMapLoaded = false, selItem = null, mapTimer = 0;
  const markers = [], markerItems = new Map();

  // Build city+state mappings for filtering.
  const cityToState = {}, stateToCities = {};
  items.forEach(i => {
    i._text = i.textContent.toLowerCase();
    i._aliases = (i.dataset.cityAliases || '').toLowerCase();
    const { city, state } = i.dataset;
    if (city && state) {
      cityToState[city] = state;
      (stateToCities[state] ||= new Set()).add(city);
    }
  });

  // Checkbox groups for bulk toggling.
  const groupBoxes = {};
  elToggles.forEach(t => {
    if (t.dataset.toggle) groupBoxes[t.dataset.toggle] = $$(`input[name="${t.dataset.toggle}"]`);
  });

  // Map logic.
  function loadMap() {
    if (isMapLoaded || isMobile) return;

    // Lazy-load only if it's enabled + not mobile.
    isMapLoaded = true;
    document.head.append(
      Object.assign(document.createElement('link'), { rel: 'stylesheet', href: 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css' })
    );

    const s = Object.assign(document.createElement('script'), { src: 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js' });
    s.onload = initMap;
    document.head.append(s);
  }

  const defStyle = { radius: 7, color: '#fff', weight: 1.5, fillColor: 'blue', fillOpacity: 0.85 };
  const hiStyle  = { radius: 10, color: '#fff', weight: 2,   fillColor: 'blue', fillOpacity: 1 };

  function styleMarker(m, style, open) {
    m.setStyle(style); m.setRadius(style.radius);
    if (open) { m.bringToFront(); m.openPopup(); } else m.closePopup();
  }

  // Initialize map with LeafletJS. Dim non-India areas.
  function initMap() {
    if (!$('#map') || typeof L === 'undefined') return;

    map = L.map('map', { maxBounds: [[5, 67], [38, 98]], maxBoundsViscosity: 1, minZoom: 4 }).setView([22, 79], 5);
    map.on('moveend', onMapMove);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd'
    }).addTo(map);

    const addLabels = () => L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png',
      { subdomains: 'abcd', pane: 'shadowPane' }
    ).addTo(map);

    // Fetch India's boundaries and apply to the map.
    fetch('/india.geojson').then(r => r.json()).then(india => {
      const world = [[-90, -180], [-90, 180], [90, 180], [90, -180]];
      const polys = india.geometry.type === 'Polygon' ? [india.geometry.coordinates] : india.geometry.coordinates;
      L.polygon([world, ...polys.map(p => p[0].map(c => [c[1], c[0]]))], {
        color: 'none', fillColor: '#ddd', fillOpacity: 0.6, interactive: false
      }).addTo(map);
      addLabels();
    }).catch(addLabels);

    items.forEach(item => {
      const lat = parseFloat(item.dataset.lat), lng = parseFloat(item.dataset.lng);
      if (isNaN(lat) || isNaN(lng)) return;

      // Build the pin-popup card.
      const q = [item.dataset.name, item.dataset.address, item.dataset.city].filter(Boolean).join(', ');
      const popup = `<strong>${item.dataset.name}</strong>`
        + (item.dataset.address ? `<br><span class="popup-address">${item.dataset.address}</span>` : '')
        + `<br><a href="https://www.google.com/maps/search/${encodeURIComponent(q)}" target="_blank" rel="noopener">Search on Google Maps &rarr;</a>`;
      const marker = L.circleMarker([lat, lng], defStyle).bindPopup(popup, { autoClose: false }).addTo(map);
      markers.push({ marker, item });
      markerItems.set(item, marker);

      item.addEventListener('mouseenter', () => {
        if (selItem === item) return;
        styleMarker(marker, hiStyle, true);
      });
      item.addEventListener('mouseleave', () => {
        if (selItem === item) return;
        styleMarker(marker, defStyle, false);
      });
      item.addEventListener('click', () => {
        if (selItem) {
          selItem.setAttribute('aria-selected', 'false');
          const prev = markerItems.get(selItem);
          if (prev) {
            styleMarker(prev, defStyle, false);
          }
        }
        if (selItem === item) {
          selItem = null;
          return;
        }

        selItem = item;
        item.setAttribute('aria-selected', 'true');
        styleMarker(marker, hiStyle, true);
      });
      marker.on('mouseover', () => {
        if (selItem !== item) styleMarker(marker, hiStyle, true);
      });
      marker.on('mouseout', () => {
        if (selItem !== item) styleMarker(marker, defStyle, false);
      });
      marker.on('click', () => {
        if (selItem) {
          selItem.setAttribute('aria-selected', 'false');
          const prev = markerItems.get(selItem);
          if (prev) styleMarker(prev, defStyle, false);
        }
        if (selItem === item) {
          selItem = null;
          return;
        }
        selItem = item;
        item.setAttribute('aria-selected', 'true');
        styleMarker(marker, hiStyle, true);
        item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    });
    updateMap();
  }

  function updateMap() {
    if (!map || elMap?.style.display === 'none') return;

    const bounds = [];
    markers.forEach(({ marker, item }) => {
      item.hidden ? marker.remove() : (marker.addTo(map), bounds.push(marker.getLatLng()));
    });
    if (!bounds.length) return;

    map.off('moveend', onMapMove);
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 });
    map.once('moveend', () => map.on('moveend', onMapMove));
  }

  function onMapMove() {
    if (!map) return;
    const bounds = map.getBounds();
    let n = 0;
    items.forEach(item => {
      if (!item._filterMatch) return;
      const marker = markerItems.get(item);
      if (marker) {
        const inView = bounds.contains(marker.getLatLng());
        item.hidden = !inView;
        if (inView) n++;
      } else {
        n++;
      }
    });
    elCount.textContent = n;
  }

  // Filtering logic.
  function cascadeFilters(changed) {
    const cb = groupBoxes.city, sb = groupBoxes.state;
    if (!cb || !sb) return;

    if (changed.name === 'city') {
      const need = new Set();
      cb.forEach(c => {
        if (c.checked && cityToState[c.value]) {
          need.add(cityToState[c.value]);
        }
      });
      sb.forEach(c => { c.checked = need.has(c.value); });
    } else if (changed.name === 'state') {
      const need = new Set();
      sb.forEach(c => {
        if (c.checked) {
          (stateToCities[c.value] || []).forEach(v => need.add(v));
        }
      });
      cb.forEach(c => { c.checked = need.has(c.value); });
    }
  }

  function updateToggleLabels() {
    elToggles.forEach(t => {
      const boxes = groupBoxes[t.dataset.toggle];
      if (!boxes) return;

      t.textContent = Array.from(boxes).every(c => c.checked) ? 'Unselect all' : 'Select all';
    });
  }

  function filter() {
    const q = (elSearch?.value || '').toLowerCase();
    const active = {};

    elChk.forEach(cb => {
      if (cb.checked) {
        (active[cb.name] ||= []).push(cb.value);
      }
    });

    let n = 0;
    items.forEach(item => {
      const show = (!q || item._text.includes(q) || item._aliases.includes(q)) && Object.entries(active).every(([k, v]) =>
        k === 'category' ? v.some(x => item.dataset.categories.split(',').includes(x)) : v.includes(item.dataset[k])
      );
      item.hidden = !show;
      item._filterMatch = show;

      if (show) {
        n++;
      }
    });
    elCount.textContent = n;
    clearTimeout(mapTimer);
    mapTimer = setTimeout(updateMap, 500);
  }

  // Bind various control events.
  elSearch?.addEventListener('input', filter);

  elChk.forEach(cb => cb.addEventListener('change', e => {
    cascadeFilters(e.target); updateToggleLabels(); filter();
  }));

  elShowMap?.addEventListener('change', () => {
    if (!elMap) return;
    localStorage.setItem('showMap', elShowMap.checked);
    if (elShowMap.checked) {
      elMap.style.display = '';
      isMapLoaded ? (map?.invalidateSize(), updateMap()) : loadMap();
    } else elMap.style.display = 'none';
  });

  elToggles.forEach(t => t.addEventListener('click', e => {
    e.preventDefault();
    const boxes = groupBoxes[t.dataset.toggle];
    if (!boxes) return;
    const all = Array.from(boxes).every(c => c.checked);
    boxes.forEach(c => c.checked = !all);
    updateToggleLabels(); filter();
  }));

  // Restore map preference from localStorage.
  if (elShowMap && localStorage.getItem('showMap') === 'false') {
    elShowMap.checked = false;
    if (elMap) elMap.style.display = 'none';
  }

  // On mobile, just don't show the map.
  if (isMobile) {
    if (elShowMap) {
      elShowMap.closest('label').style.display = 'none';
      elShowMap.checked = false; 
    }
    if (elMap) {
      elMap.style.display = 'none';
    }
  } else if (!elShowMap || elShowMap?.checked) {
    loadMap();
  }

  // Filter toggle for mobile.
  const elFilterToggle = $('#filter-toggle');
  const elFilterGroups = $('.filter-groups');
  if (elFilterToggle && elFilterGroups) {
    elFilterToggle.addEventListener('click', e => {
      e.preventDefault();
      const open = elFilterGroups.classList.toggle('open');
      elFilterToggle.textContent = open ? 'Hide filters' : 'Show filters';
    });
  }

  // Reset all controls on boot.
  if (elSearch) elSearch.value = '';
  elChk.forEach(cb => cb.checked = true);
  updateToggleLabels(); filter();
});
