/* Motion player shell. Plain script, no modules, so it runs over file://.
   Exposes window.VconMotion. scene-authoring.md in this folder defines the scene API. */
(function (global) {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';
  var DEFAULT_HOLD = 700;      // ms pause after a step while playing
  var REDUCED_MIN_HOLD = 2500; // ms a step stays up when motion is reduced
  var MAX_FRAME = 100;         // ms, so a stalled tab does not jump a step

  var TOKENS = Object.freeze({
    green: '#0BB81E',
    greenDeep: '#0A7D18',
    ink: '#292929',
    body: '#33363B',
    muted: '#8A8A8D',
    surface: '#F3F4F6',
    white: '#FFFFFF'
  });

  var scenes = {};
  var dom = {};
  var motionQuery = global.matchMedia
    ? global.matchMedia('(prefers-reduced-motion: reduce)')
    : { matches: false };

  // Player state. cursor counts finished steps, from 0 to steps.length.
  var scene = null;
  var sceneId = null;
  var ctx = null;
  var cursor = 0;
  var progress = 0;
  var elapsed = 0;
  var holdLeft = 0;
  var playing = false;
  var rafId = null;
  var lastTs = null;
  var errorText = null;

  /* ---------- Maths ---------- */

  function clamp(v, lo, hi) {
    if (lo === undefined) { lo = 0; }
    if (hi === undefined) { hi = 1; }
    return Math.min(hi, Math.max(lo, v));
  }

  function lerp(a, b, p) { return a + (b - a) * p; }

  // Maps p to 0..1 across the window a..b of a step.
  function seg(p, a, b) { return clamp((p - a) / (b - a)); }

  function bezier(a, b, t) {
    var u = 1 - t;
    return 3 * u * u * t * a + 3 * u * t * t * b + t * t * t;
  }

  // Brand easing, cubic-bezier(.2, .7, .2, 1).
  function ease(p) {
    if (p <= 0) { return 0; }
    if (p >= 1) { return 1; }
    var lo = 0;
    var hi = 1;
    for (var i = 0; i < 24; i++) {
      var mid = (lo + hi) / 2;
      if (bezier(0.2, 0.2, mid) < p) { lo = mid; } else { hi = mid; }
    }
    return bezier(0.7, 1, (lo + hi) / 2);
  }

  /* ---------- Stage helpers handed to scenes as ctx ---------- */

  function setAttrs(node, attrs) {
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    return node;
  }

  function createCtx(svg, width, height) {
    function layer(name) {
      var g = document.createElementNS(SVG_NS, 'g');
      g.setAttribute('data-layer', name);
      svg.appendChild(g);
      return g;
    }

    var layers = {
      back: layer('back'),
      edges: layer('edges'),
      nodes: layer('nodes'),
      tokens: layer('tokens'),
      notes: layer('notes')
    };

    function el(tag, attrs, parent) {
      var node = setAttrs(document.createElementNS(SVG_NS, tag), attrs);
      (parent || layers.notes).appendChild(node);
      return node;
    }

    function setText(node, value) {
      var x = node.getAttribute('x') || 0;
      while (node.firstChild) { node.removeChild(node.firstChild); }
      String(value).split('\n').forEach(function (line, i) {
        var span = el('tspan', { x: x, dy: i === 0 ? 0 : '1.3em' }, node);
        span.textContent = line;
      });
      return node;
    }

    function text(opts) {
      var cls = 'mo-svg-text' + (opts.kind ? ' mo-svg-text--' + opts.kind : '');
      var node = el('text', {
        x: opts.x,
        y: opts.y,
        'class': cls,
        'text-anchor': opts.anchor || 'start'
      }, opts.parent);
      return setText(node, opts.text);
    }

    function stateSetter(target, base) {
      return function (state) {
        var cls = base + (state && state !== 'idle' ? ' ' + base + '--' + state : '');
        target.setAttribute('class', cls + (target.__moExtra || ''));
      };
    }

    function show(node, visible) {
      var target = node.g || node;
      target.setAttribute('visibility', visible === false ? 'hidden' : 'visible');
    }

    function fade(node, opacity) {
      (node.g || node).setAttribute('opacity', clamp(opacity));
    }

    function node(opts) {
      var w = opts.w || 150;
      var h = opts.h || 64;
      var x = opts.x;
      var y = opts.y;
      var cx = x + w / 2;
      var cy = y + h / 2;
      var g = el('g', { 'class': 'mo-node' }, layers.nodes);
      el('rect', { x: x, y: y, width: w, height: h }, g);
      var label = el('text', {
        x: cx,
        'class': 'mo-node-label',
        'text-anchor': 'middle',
        'dominant-baseline': 'central'
      }, g);
      var sub = el('text', {
        x: cx,
        'class': 'mo-node-sub',
        'text-anchor': 'middle',
        'dominant-baseline': 'central'
      }, g);

      function setLabel(main, detail) {
        label.setAttribute('y', detail ? cy - 9 : cy);
        sub.setAttribute('y', cy + 12);
        label.textContent = main;
        sub.textContent = detail || '';
      }

      setLabel(opts.label || '', opts.sub);
      var api = {
        g: g, x: x, y: y, w: w, h: h, cx: cx, cy: cy,
        left: [x, cy], right: [x + w, cy], top: [cx, y], bottom: [cx, y + h],
        setLabel: setLabel,
        setState: stateSetter(g, 'mo-node')
      };
      if (opts.state) { api.setState(opts.state); }
      return api;
    }

    function edge(opts) {
      var points = [opts.from].concat(opts.via || [], [opts.to]);
      var lengths = [0];
      for (var i = 1; i < points.length; i++) {
        lengths.push(lengths[i - 1] + Math.hypot(
          points[i][0] - points[i - 1][0],
          points[i][1] - points[i - 1][1]
        ));
      }
      var total = lengths[lengths.length - 1];

      function pointAt(p) {
        var target = clamp(p) * total;
        for (var j = 1; j < points.length; j++) {
          if (target <= lengths[j] || j === points.length - 1) {
            var span = (lengths[j] - lengths[j - 1]) || 1;
            var t = (target - lengths[j - 1]) / span;
            return [
              lerp(points[j - 1][0], points[j][0], t),
              lerp(points[j - 1][1], points[j][1], t)
            ];
          }
        }
        return points[0];
      }

      var g = el('g', {}, layers.edges);
      g.__moExtra = opts.dashed ? ' mo-edge--dashed' : '';
      var setState = stateSetter(g, 'mo-edge');
      setState(opts.state || 'idle');

      el('path', {
        d: points.map(function (pt, k) {
          return (k === 0 ? 'M' : 'L') + pt[0] + ' ' + pt[1];
        }).join(' ')
      }, g);

      var tip = points[points.length - 1];
      var prev = points[points.length - 2];
      var angle = Math.atan2(tip[1] - prev[1], tip[0] - prev[0]) * 180 / Math.PI;
      el('polygon', {
        points: '0,0 -10,-5 -10,5',
        transform: 'translate(' + tip[0] + ' ' + tip[1] + ') rotate(' + angle + ')'
      }, g);

      if (opts.label) {
        var mid = pointAt(0.5);
        text({ x: mid[0], y: mid[1] - 8, text: opts.label, anchor: 'middle', parent: g });
      }

      return { g: g, points: points, pointAt: pointAt, setState: setState };
    }

    function token(opts) {
      var label = opts.label || 'vCon';
      var w = opts.w || label.length * 8 + 20;
      var h = opts.h || 26;
      var g = el('g', { 'class': 'mo-token' }, layers.tokens);
      el('rect', { x: -w / 2, y: -h / 2, width: w, height: h }, g);
      var caption = el('text', { 'text-anchor': 'middle', 'dominant-baseline': 'central' }, g);
      caption.textContent = label;

      var api = {
        g: g,
        at: function (x, y) {
          g.setAttribute('transform', 'translate(' + x + ' ' + y + ')');
        },
        follow: function (path, p) {
          var pt = path.pointAt(p);
          api.at(pt[0], pt[1]);
        },
        setLabel: function (value) { caption.textContent = value; },
        setState: stateSetter(g, 'mo-token')
      };
      api.at(opts.x || 0, opts.y || 0);
      if (opts.state) { api.setState(opts.state); }
      if (opts.hidden) { show(g, false); }
      return api;
    }

    return {
      svg: svg,
      width: width,
      height: height,
      layers: layers,
      tokens: TOKENS,
      state: {},
      reducedMotion: motionQuery.matches,
      el: el,
      text: text,
      setText: setText,
      node: node,
      edge: edge,
      token: token,
      show: show,
      fade: fade,
      ease: ease,
      lerp: lerp,
      clamp: clamp,
      seg: seg
    };
  }

  /* ---------- Rendering ---------- */

  function fail(message, err) {
    errorText = message;
    stopLoop();
    if (err) { global.console.error(message, err); } else { global.console.error(message); }
    dom.stage.textContent = '';
    var p = document.createElement('p');
    p.className = 'mo-error';
    p.textContent = message;
    dom.stage.appendChild(p);
    sync();
  }

  function mount() {
    var box = scene.viewBox || [960, 540];
    var svg = setAttrs(document.createElementNS(SVG_NS, 'svg'), {
      viewBox: '0 0 ' + box[0] + ' ' + box[1],
      role: 'img',
      'aria-label': scene.title + '. ' + (scene.summary || '')
    });
    dom.stage.textContent = '';
    dom.stage.appendChild(svg);
    ctx = createCtx(svg, box[0], box[1]);
    try {
      scene.setup(ctx);
      return true;
    } catch (err) {
      fail('Scene ' + sceneId + ' failed in setup: ' + err.message, err);
      return false;
    }
  }

  function draw(step, p) {
    try {
      step.draw(p, ctx);
      return true;
    } catch (err) {
      fail('Scene ' + sceneId + ' failed in step ' + step.id + ': ' + err.message, err);
      return false;
    }
  }

  // Every jump rebuilds the stage and replays finished steps at p = 1, so a
  // frame depends only on the position and never on how the viewer got there.
  function renderAt(nextCursor, p) {
    if (!mount()) { return; }
    for (var i = 0; i < nextCursor; i++) {
      if (!draw(scene.steps[i], 1)) { return; }
    }
    cursor = nextCursor;
    progress = cursor < scene.steps.length ? p : 0;
    elapsed = progress * (cursor < scene.steps.length ? scene.steps[cursor].duration : 0);
    holdLeft = 0;
    if (progress > 0 && !draw(scene.steps[cursor], progress)) { return; }
    sync();
  }

  function activeIndex() {
    return progress > 0 ? cursor : cursor - 1;
  }

  function sync() {
    var count = scene ? scene.steps.length : 0;
    var usable = count > 0 && errorText === null;
    var done = usable && cursor >= count;
    var active = activeIndex();
    var caption = '';
    if (usable) {
      caption = active >= 0 ? scene.steps[active].caption : 'Press Play or Step to start.';
    }

    dom.play.textContent = playing ? 'Pause' : (done ? 'Replay' : 'Play');
    dom.play.disabled = !usable;
    dom.back.disabled = !usable || (cursor === 0 && progress === 0);
    dom.step.disabled = !usable || done;
    dom.reset.disabled = !usable;
    dom.progress.style.width = count ? ((cursor + progress) / count * 100) + '%' : '0';
    dom.status.textContent = usable ? 'Step ' + Math.max(active + 1, 0) + ' of ' + count : '';
    if (dom.caption.textContent !== caption) { dom.caption.textContent = caption; }
    dom.reducedNote.hidden = !motionQuery.matches;

    Array.prototype.forEach.call(dom.steps.querySelectorAll('.mo-step'), function (button, i) {
      if (i === active) {
        button.setAttribute('aria-current', 'step');
      } else {
        button.removeAttribute('aria-current');
      }
    });
  }

  /* ---------- Playback ---------- */

  function stopLoop() {
    playing = false;
    lastTs = null;
    if (rafId !== null) {
      global.cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  function holdAfter(step) {
    var hold = step.hold === undefined ? DEFAULT_HOLD : step.hold;
    return motionQuery.matches ? Math.max(step.duration + hold, REDUCED_MIN_HOLD) : hold;
  }

  function tick(ts) {
    rafId = null;
    if (!playing) { return; }
    var dt = lastTs === null ? 0 : Math.min(ts - lastTs, MAX_FRAME);
    lastTs = ts;

    if (holdLeft > 0) {
      holdLeft -= dt;
      if (holdLeft > 0) {
        rafId = global.requestAnimationFrame(tick);
        return;
      }
      holdLeft = 0;
    }

    var step = scene.steps[cursor];
    elapsed += dt;
    var instant = motionQuery.matches || step.duration === 0;
    var p = instant ? 1 : Math.min(elapsed / step.duration, 1);
    if (!draw(step, p)) { return; }
    progress = p;

    if (p >= 1) {
      cursor += 1;
      progress = 0;
      elapsed = 0;
      holdLeft = cursor < scene.steps.length ? holdAfter(step) : 0;
    }

    if (cursor >= scene.steps.length) {
      stopLoop();
    } else {
      rafId = global.requestAnimationFrame(tick);
    }
    sync();
  }

  function play() {
    if (!scene || errorText !== null || playing) { return; }
    if (cursor >= scene.steps.length) { renderAt(0, 0); }
    playing = true;
    lastTs = null;
    rafId = global.requestAnimationFrame(tick);
    sync();
  }

  function pause() {
    if (!playing) { return; }
    stopLoop();
    holdLeft = 0;
    sync();
  }

  function seek(nextCursor, p) {
    if (!scene || errorText !== null) { return; }
    stopLoop();
    renderAt(clamp(Math.round(nextCursor), 0, scene.steps.length), clamp(p || 0));
  }

  // step() finishes the current step. step(-1) returns to the start of the
  // current step, or to the start of the one before if already at a boundary.
  function step(delta) {
    if (!scene) { return; }
    if (delta !== undefined && delta < 0) {
      seek(progress > 0 ? cursor : cursor - 1);
    } else {
      seek(cursor + 1);
    }
  }

  function reset() { seek(0); }

  /* ---------- Scene selection ---------- */

  function fillSceneChrome() {
    var tab = document.getElementById('tab-' + sceneId);
    var fallback = tab ? tab.textContent.replace(/^M\d+/, '') : sceneId;
    dom.title.textContent = scene ? scene.title : fallback;
    dom.summary.textContent = scene ? (scene.summary || '') : '';

    dom.steps.textContent = '';
    (scene ? scene.steps : []).forEach(function (item, i) {
      var li = document.createElement('li');
      var button = document.createElement('button');
      var strong = document.createElement('strong');
      button.type = 'button';
      button.className = 'mo-step';
      strong.textContent = (i + 1) + '. ' + item.label;
      button.appendChild(strong);
      button.appendChild(document.createTextNode(item.caption));
      button.addEventListener('click', function () { seek(i + 1); });
      li.appendChild(button);
      dom.steps.appendChild(li);
    });

    dom.twins.textContent = '';
    (scene && scene.twins ? scene.twins : []).forEach(function (slug) {
      var a = document.createElement('a');
      a.href = '../../diagrams/' + slug + '.svg';
      a.textContent = slug.split('-')[0];
      a.title = slug;
      dom.twins.appendChild(a);
    });
  }

  function select(id) {
    var key = String(id).toLowerCase();
    var tab = document.getElementById('tab-' + key);
    if (!tab || key === sceneId) { return; }

    stopLoop();
    sceneId = key;
    scene = scenes[key] || null;
    cursor = 0;
    progress = 0;
    elapsed = 0;
    holdLeft = 0;
    errorText = null;

    dom.tabs.forEach(function (item) {
      var selected = item === tab;
      item.setAttribute('aria-selected', selected ? 'true' : 'false');
      item.tabIndex = selected ? 0 : -1;
    });
    dom.player.setAttribute('aria-labelledby', tab.id);
    if (global.location.hash !== '#' + key) { global.location.hash = key; }

    fillSceneChrome();
    if (!scene) {
      fail('Scene ' + key + ' did not register. Check its file in scenes/ and the browser console.');
      return;
    }
    renderAt(0, 0);
  }

  function onTabKey(event) {
    var index = dom.tabs.indexOf(event.currentTarget);
    var last = dom.tabs.length - 1;
    var next = {
      ArrowRight: index === last ? 0 : index + 1,
      ArrowLeft: index === 0 ? last : index - 1,
      Home: 0,
      End: last
    }[event.key];
    if (next === undefined) { return; }
    event.preventDefault();
    dom.tabs[next].focus();
    select(dom.tabs[next].dataset.scene);
  }

  function boot() {
    function byId(id) { return document.getElementById(id); }
    dom = {
      player: byId('player'),
      stage: byId('stage'),
      title: byId('scene-title'),
      summary: byId('scene-summary'),
      progress: byId('progress'),
      play: byId('btn-play'),
      back: byId('btn-back'),
      step: byId('btn-step'),
      reset: byId('btn-reset'),
      status: byId('status'),
      caption: byId('caption'),
      reducedNote: byId('reduced-note'),
      steps: byId('steps'),
      twins: byId('twins'),
      tabs: Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'))
    };

    dom.tabs.forEach(function (tab) {
      tab.addEventListener('click', function () { select(tab.dataset.scene); });
      tab.addEventListener('keydown', onTabKey);
    });
    dom.play.addEventListener('click', function () { if (playing) { pause(); } else { play(); } });
    dom.back.addEventListener('click', function () { step(-1); });
    dom.step.addEventListener('click', function () { step(); });
    dom.reset.addEventListener('click', reset);

    global.addEventListener('hashchange', function () {
      select(global.location.hash.slice(1));
    });
    if (motionQuery.addEventListener) {
      motionQuery.addEventListener('change', function () {
        if (ctx) { ctx.reducedMotion = motionQuery.matches; }
        sync();
      });
    }

    var wanted = global.location.hash.slice(1).toLowerCase();
    select(document.getElementById('tab-' + wanted) ? wanted : dom.tabs[0].dataset.scene);
  }

  /* ---------- Public API ---------- */

  function register(def) {
    function bad(why) {
      throw new TypeError('VconMotion.register(' + (def && def.id) + '): ' + why);
    }
    if (!def || !/^m[0-9]+$/.test(def.id || '')) { bad('id must look like m1'); }
    if (typeof def.title !== 'string' || !def.title) { bad('title is required'); }
    if (typeof def.setup !== 'function') { bad('setup must be a function'); }
    if (!Array.isArray(def.steps) || def.steps.length === 0) { bad('steps must not be empty'); }
    def.steps.forEach(function (item, i) {
      var where = 'step ' + i + ' ';
      if (!item.id) { bad(where + 'needs an id'); }
      if (!item.label) { bad(where + 'needs a label'); }
      if (!item.caption) { bad(where + 'needs a caption'); }
      if (typeof item.duration !== 'number' || item.duration < 0) { bad(where + 'needs a duration in ms'); }
      if (typeof item.draw !== 'function') { bad(where + 'needs a draw function'); }
    });
    scenes[def.id] = def;
  }

  function state() {
    var count = scene ? scene.steps.length : 0;
    return {
      scene: sceneId,
      title: scene ? scene.title : null,
      cursor: cursor,
      progress: progress,
      stepCount: count,
      activeStep: scene && activeIndex() >= 0 ? scene.steps[activeIndex()].id : null,
      playing: playing,
      done: count > 0 && cursor >= count,
      reducedMotion: motionQuery.matches,
      error: errorText
    };
  }

  global.VconMotion = {
    register: register,
    select: select,
    play: play,
    pause: pause,
    step: step,
    seek: seek,
    reset: reset,
    state: state,
    scenes: function () { return Object.keys(scenes).sort(); }
  };

  document.addEventListener('DOMContentLoaded', boot);
}(window));
