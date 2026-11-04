/* M2. Workers drain the ingress queues. Static twin: D06-worker-queue-topology.
   Every step comment names the code the step draws. Line numbers refer to the
   worktree at the time of writing. The ids and the two lists are a made-up run;
   only their behaviour comes from the code.

   Layout follows D06: producers on the left, ingress lists next, the main process
   and two worker processes in the middle, and the output lists on the right. The
   scene shows two workers. CONSERVER_WORKERS sets the real count. */
VconMotion.register({
  id: 'm2',
  title: 'Workers drain the ingress queues',
  summary: 'Worker processes pop vCon ids from Redis ingress lists with BLPOP, run one chain per id, and send each id to egress, storage or a dead letter list.',
  twins: ['D06-worker-queue-topology'],

  setup: function (ctx) {
    var s = ctx.state;
    s.nodes = [];
    s.wires = [];

    function box(opts) {
      var n = ctx.node(opts);
      s.nodes.push(n);
      return n;
    }

    // A wire is a grey edge plus a lit copy on top, so a lit path stays visible
    // where several wires share the rail on the right.
    function wire(opts) {
      var base = ctx.edge(opts);
      var over = ctx.edge({ from: opts.from, to: opts.to, via: opts.via, dashed: opts.dashed, state: 'active' });
      ctx.show(over, false);
      var w = {
        points: base.points,
        pointAt: base.pointAt,
        over: over,
        on: function (state) {
          over.setState(state || 'active');
          ctx.show(over, true);
        },
        off: function () { ctx.show(over, false); }
      };
      s.wires.push(w);
      return w;
    }

    // An invisible path for a token to follow.
    function route(points) {
      var e = ctx.edge({ from: points[0], to: points[points.length - 1], via: points.slice(1, -1) });
      ctx.show(e, false);
      return e;
    }

    function frame(x, y, w, h) {
      return ctx.el('rect', {
        x: x, y: y, width: w, height: h, rx: 2,
        fill: ctx.tokens.white, stroke: ctx.tokens.muted, 'stroke-width': 1.5
      }, ctx.layers.back);
    }

    /* ---------- Producers ---------- */
    ctx.text({ x: 14, y: 116, text: 'Producers', kind: 'title' });
    s.api = box({ x: 14, y: 130, w: 160, h: 56, label: 'API ingress routes', sub: 'three POST routes' });
    s.follower = box({ x: 14, y: 212, w: 160, h: 56, label: 'Follower timers', sub: 'in the main process' });
    s.replay = box({ x: 14, y: 452, w: 180, h: 56, label: 'POST /dlq/reprocess', sub: 'API replay route' });

    /* ---------- Ingress lists, head on the right ---------- */
    frame(196, 120, 154, 226);
    ctx.text({ x: 273, y: 142, text: 'Ingress lists', kind: 'label', anchor: 'middle' });
    ctx.text({ x: 206, y: 168, text: 'List A, scanned first', kind: 'small' });
    ctx.text({ x: 206, y: 256, text: 'List B, scanned next', kind: 'small' });
    [176, 264].forEach(function (y) {
      ctx.el('rect', {
        x: 206, y: y, width: 134, height: 38,
        fill: ctx.tokens.surface, stroke: ctx.tokens.muted, 'stroke-width': 1
      }, ctx.layers.back);
      ctx.text({ x: 206, y: y + 52, text: 'tail', kind: 'small' });
      ctx.text({ x: 340, y: y + 52, text: 'head', kind: 'small', anchor: 'end' });
    });
    s.timer = ctx.text({ x: 273, y: 366, text: '', kind: 'small', anchor: 'middle' });

    /* ---------- Conserver ---------- */
    frame(392, 32, 344, 394);
    ctx.text({ x: 402, y: 48, text: 'Conserver', kind: 'title' });
    s.main = box({
      x: 420, y: 54, w: 298, h: 46,
      label: 'Main process', sub: 'spawns CONSERVER_WORKERS processes'
    });

    s.workers = [108, 266].map(function (top, i) {
      var w = {
        top: top,
        hy: top + 53,       // height of the worker_loop and _handle_vcon centres
        rest: top + 14,     // height where a token sits above a box
        frame: frame(412, top, 314, 150)
      };
      w.title = ctx.text({ x: 568, y: top + 18, text: 'Worker-' + (i + 1), kind: 'small', anchor: 'middle' });
      w.loop = box({ x: 420, y: top + 28, w: 104, h: 50, label: 'worker_loop', sub: 'BLPOP, 15 s' });
      w.handle = box({ x: 610, y: top + 28, w: 108, h: 50, label: '_handle_vcon', sub: 'runs one chain' });
      w.pool = box({ x: 505, y: top + 94, w: 126, h: 46, label: 'Thread pool', sub: 'only above 1' });
      return w;
    });

    /* ---------- Output lists and their readers ---------- */
    var rx = 762;
    var rw = 180;
    s.reader = box({ x: rx, y: 14, w: rw, h: 50, label: 'GET /vcon/egress', sub: 'client or remote follower' });
    s.egress = box({ x: rx, y: 92, w: rw, h: 50, label: 'Egress lists', sub: 'RPUSH after links' });
    s.storage = box({ x: rx, y: 176, w: rw, h: 50, label: 'Storage backends', sub: 'save' });
    s.sdlq = box({ x: rx, y: 260, w: rw, h: 50, label: 'DLQ:storage:backend', sub: 'RPUSH on failed save' });
    s.sreplay = box({ x: rx, y: 344, w: rw, h: 50, label: 'Storage replay', sub: 'POST /dlq/storage/reprocess' });
    s.dlq = box({ x: rx, y: 452, w: rw, h: 56, label: 'DLQ:ingress_list', sub: 'RPUSH on exception' });

    /* ---------- Wires ---------- */
    s.wApi = wire({ from: s.api.right, to: [196, 158] });
    s.wFollower = wire({ from: s.follower.right, to: [196, 240] });
    s.wReplay = wire({ from: [185, 452], to: [196, 320], via: [[185, 320]] });
    s.wDlqOut = wire({ from: [rx, 494], to: [194, 494] });
    ctx.text({ x: 478, y: 486, text: 'LPOP', kind: 'small', anchor: 'middle' });

    var railX = 748;
    s.workers.forEach(function (w) {
      w.wSpawn = wire({ from: s.main.left, to: [412, w.top + 25], via: [[402, 77], [402, w.top + 25]] });
      w.wPop = wire({ from: [350, w.hy], to: w.loop.left });
      w.wPush = wire({ from: [420, w.hy + 14], to: [350, w.hy + 14], dashed: true });
      ctx.text({ x: 371, y: w.hy - 6, text: 'BLPOP', kind: 'small', anchor: 'middle' });
      ctx.text({ x: 371, y: w.hy + 29, text: 'LPUSH', kind: 'small', anchor: 'middle' });
      w.wSerial = wire({ from: w.loop.right, to: w.handle.left, label: 'concurrency 1' });
      w.wPoolIn = wire({ from: w.loop.bottom, to: w.pool.left, via: [[w.loop.cx, w.pool.cy]] });
      w.wPoolOut = wire({ from: w.pool.right, to: w.handle.bottom, via: [[w.handle.cx, w.pool.cy]] });

      function out(y) {
        return wire({ from: w.handle.right, to: [rx, y], via: [[railX, w.hy], [railX, y]] });
      }
      w.wEgress = out(s.egress.cy);
      w.wSave = out(s.storage.cy);
      w.wSdlq = out(s.sdlq.cy);
      w.wDlq = out(470);
    });

    s.wRead = wire({ from: s.egress.top, to: s.reader.bottom });
    ctx.text({ x: 860, y: 82, text: 'RPOP', kind: 'small' });
    s.wSdlqOut = wire({ from: s.sdlq.bottom, to: s.sreplay.top });
    ctx.text({ x: 860, y: 331, text: 'LRANGE, LREM', kind: 'small' });
    s.wResave = wire({ from: s.sreplay.right, to: s.storage.right, via: [[953, s.sreplay.cy], [953, s.storage.cy]] });
    s.wLoopback = wire({
      from: [rx, 103], to: [273, 120],
      via: [[755, 103], [755, 10], [273, 10]], dashed: true
    });
    ctx.text({ x: 284, y: 26, text: 'same name as an ingress list', kind: 'small' });

    // Lit copies go last so they sit above every grey wire.
    s.wires.forEach(function (w) { ctx.layers.edges.appendChild(w.over.g); });

    /* ---------- Token paths ---------- */
    var W1 = s.workers[0];
    var W2 = s.workers[1];
    var laneA = 195;
    var laneB = 283;
    var head = 318;
    var next = 273;
    var loopX = W1.loop.cx;
    var handleX = W1.handle.cx;
    var shelfX = rx + rw - 22;

    function popPath(lane, w) {
      return route([[head, lane], [371, lane], [371, w.hy], [loopX, w.hy], [loopX, w.rest]]);
    }
    function dispatchPath(w) {
      return route([[loopX, w.rest], [loopX, w.hy], [handleX, w.hy], [handleX, w.rest]]);
    }
    function outPath(w, y, shelfY) {
      return route([
        [handleX, w.rest], [handleX, w.hy], [railX, w.hy], [railX, y],
        [shelfX, y], [shelfX, shelfY]
      ]);
    }

    s.paths = {
      apiIn: route([[174, 158], [190, 158], [190, laneA], [head, laneA]]),
      followerIn: route([[174, 240], [190, 240], [190, laneA], [next, laneA]]),
      replayIn: route([[185, 452], [185, laneB], [head, laneB]]),
      shiftA: route([[next, laneA], [head, laneA]]),
      popA1: popPath(laneA, W1),
      popA2: popPath(laneA, W2),
      popB1: popPath(laneB, W1),
      dispatch1: dispatchPath(W1),
      dispatch2: dispatchPath(W2),
      toEgress: outPath(W1, s.egress.cy, s.egress.y - 5),
      toSave: outPath(W1, s.storage.cy, s.storage.y - 5),
      toDlq: outPath(W2, 470, s.dlq.y - 5),
      toSdlq: outPath(W1, s.sdlq.cy, s.sdlq.y - 5),
      read: route([[shelfX, s.egress.y - 5], [s.egress.cx, s.egress.y - 5], [s.egress.cx, s.reader.cy]]),
      resave: route([
        [shelfX, s.sdlq.y - 5], [s.sdlq.cx, s.sdlq.y - 5], [s.sdlq.cx, s.sreplay.cy],
        [953, s.sreplay.cy], [953, s.storage.cy], [shelfX + 20, s.storage.cy], [shelfX, s.storage.y - 5]
      ]),
      replayOut: route([
        [shelfX, s.dlq.y - 5], [shelfX, 494], [185, 494], [185, 320], [190, 320], [190, laneA], [head, laneA]
      ]),
      giveBack: route([
        [loopX, W1.rest], [loopX, W1.hy + 14], [350, W1.hy + 14], [340, laneA], [head, laneA]
      ])
    };

    /* ---------- Tokens ---------- */
    s.id1 = ctx.token({ x: 174, y: 158, label: 'id 1', w: 40, hidden: true });
    s.id2 = ctx.token({ x: 174, y: 240, label: 'id 2', w: 40, hidden: true });
    s.id3 = ctx.token({ x: 185, y: 452, label: 'id 3', w: 40, hidden: true });
    s.id4 = ctx.token({ x: 174, y: 158, label: 'id 4', w: 40, hidden: true });
    s.body = ctx.token({ x: handleX, y: W1.rest, label: 'vCon', w: 44, hidden: true });

    // Workers do not exist until step 2 runs.
    s.setWorkers = function (opacity) {
      s.workers.forEach(function (w) {
        ctx.fade(w.frame, opacity);
        ctx.fade(w.title, opacity);
        ctx.fade(w.loop, opacity);
        ctx.fade(w.handle, opacity);
        ctx.fade(w.pool, opacity);
      });
    };
    s.setWorkers(0.3);

    // Clears the highlights of the step before. Tokens keep their place.
    s.calm = function () {
      s.nodes.forEach(function (n) { n.setState('idle'); });
      s.wires.forEach(function (w) { w.off(); });
    };

    // Moves a token along a path. A window that has not opened leaves it alone.
    s.ride = function (token, path, q) {
      if (q <= 0) { return; }
      ctx.show(token, true);
      token.follow(path, ctx.ease(q));
    };
  },

  steps: [
    {
      // API: api/api.py:806 (POST /vcon), :908 (external-ingress), :1046 (ingress),
      // through VconQueue.enqueue_async at common/lib/queue.py:158.
      // Follower: conserver/follower.py:50, VconQueue.enqueue at common/lib/queue.py:64.
      // Replay: api/api.py:1171. Body key: _vcon_key at common/lib/queue.py:41.
      id: 'producers-push',
      label: 'Producers push vCon ids',
      caption: 'The API ingress routes, the follower timers and POST /dlq/reprocess RPUSH vCon ids onto the tail of an ingress list. The list holds ids only, and each vCon body sits under its own Redis key.',
      duration: 2000,
      draw: function (p, ctx) {
        var s = ctx.state;
        s.calm();
        s.api.setState('active');
        s.follower.setState('active');
        s.replay.setState('active');
        s.wApi.on();
        s.wFollower.on();
        s.wReplay.on();
        s.ride(s.id1, s.paths.apiIn, ctx.seg(p, 0, 0.6));
        s.ride(s.id2, s.paths.followerIn, ctx.seg(p, 0.2, 0.8));
        s.ride(s.id3, s.paths.replayIn, ctx.seg(p, 0.4, 1));
      }
    },
    {
      // Spawn loop: conserver/main.py:993 to :1004. Count: get_worker_count at
      // common/config.py:15, from common/settings.py:63. Single worker: main.py:1048.
      id: 'main-spawns-workers',
      label: 'The main process spawns workers',
      caption: 'With CONSERVER_WORKERS above 1, main() starts that many processes and each one runs worker_loop. With a count of 1, the main process runs worker_loop itself.',
      duration: 1400,
      draw: function (p, ctx) {
        var s = ctx.state;
        s.calm();
        s.main.setState('active');
        s.workers.forEach(function (w) { w.wSpawn.on(); });
        s.setWorkers(ctx.lerp(0.3, 1, ctx.ease(p)));
      }
    },
    {
      // Config reread: conserver/main.py:862. Ingress map: main.py:673, :865, :866.
      // BLPOP: main.py:875, VconQueue.dequeue at common/lib/queue.py:81 to :90.
      // Atomic hand-out: worker_loop docstring, main.py:777.
      id: 'blpop-pops-heads',
      label: 'BLPOP gives each worker one id',
      caption: 'Each pass rereads the config, then BLPOP watches every ingress list with a 15 s timeout. It pops the head of the first non-empty list in chain order, so each id reaches one worker and id 3 waits on list B.',
      duration: 2000,
      draw: function (p, ctx) {
        var s = ctx.state;
        var a = s.workers[0];
        var b = s.workers[1];
        s.calm();
        a.loop.setState('active');
        b.loop.setState('active');
        a.wPop.on();
        b.wPop.on();
        s.ride(s.id1, s.paths.popA1, ctx.seg(p, 0, 0.5));
        s.ride(s.id2, s.paths.shiftA, ctx.seg(p, 0.3, 0.5));
        s.ride(s.id2, s.paths.popA2, ctx.seg(p, 0.5, 1));
      }
    },
    {
      // Serial path: conserver/main.py:903 to :905. _handle_vcon: main.py:702.
      // The next BLPOP comes only after _handle_vcon returns.
      id: 'serial-dispatch',
      label: 'Each worker runs one chain',
      caption: 'At concurrency 1, worker_loop calls _handle_vcon directly. It pops nothing more until that chain ends.',
      duration: 1400,
      draw: function (p, ctx) {
        var s = ctx.state;
        s.calm();
        s.workers.forEach(function (w) {
          w.wSerial.on();
          w.handle.setState('active');
        });
        s.ride(s.id1, s.paths.dispatch1, p);
        s.ride(s.id2, s.paths.dispatch2, p);
      }
    },
    {
      // Pool: conserver/main.py:850 to :851, submit at :908, back-pressure at :914.
      // Setting: common/settings.py:81, get_vcon_concurrency at common/config.py:33.
      id: 'thread-pool',
      label: 'A thread pool adds in-flight vCons',
      caption: 'Above 1, each worker submits _handle_vcon to a pool of CONSERVER_VCON_CONCURRENCY threads. worker_loop stops popping while the pool is full.',
      duration: 1000,
      hold: 1200,
      draw: function (p, ctx) {
        var s = ctx.state;
        s.calm();
        s.workers.forEach(function (w) {
          w.wPoolIn.on();
          w.wPoolOut.on();
          w.pool.setState('active');
        });
      }
    },
    {
      // _wrap_up: conserver/main.py:345, called at :273. Egress first: :352 to :366.
      // Storage next: :368 to :382, Storage(name).save at :410.
      id: 'wrap-up',
      label: 'The chain ends in egress and storage',
      caption: 'When the links finish, _wrap_up pushes the id onto each egress list of the chain, then saves the vCon to each storage backend.',
      duration: 1800,
      draw: function (p, ctx) {
        var s = ctx.state;
        var a = s.workers[0];
        var first = ctx.seg(p, 0, 0.5);
        var second = ctx.seg(p, 0.5, 1);
        s.calm();
        a.handle.setState('active');
        if (first > 0) { a.wEgress.on(); s.egress.setState('active'); }
        if (second > 0) {
          a.wEgress.off();
          a.wSave.on();
          s.egress.setState('done');
          s.storage.setState('active');
        }
        s.ride(s.id1, s.paths.toEgress, first);
        s.ride(s.body, s.paths.toSave, second);
        if (p >= 1) {
          a.handle.setState('done');
          s.storage.setState('done');
          s.body.setState('done');
        }
      }
    },
    {
      // except branch: conserver/main.py:754 to :763. enqueue_dlq: common/lib/queue.py:92.
      // Name: get_ingress_list_dlq_name at common/dlq_utils.py:3.
      // VCON_DLQ_EXPIRY: common/settings.py:56.
      id: 'exception-to-dlq',
      label: 'An exception fills the ingress DLQ',
      caption: 'An exception in the chain pushes the id onto the DLQ named for its ingress list. When VCON_DLQ_EXPIRY is above 0, the vCon also gets that TTL.',
      duration: 1500,
      draw: function (p, ctx) {
        var s = ctx.state;
        var b = s.workers[1];
        s.calm();
        b.handle.setState('fail');
        b.wDlq.on('fail');
        s.dlq.setState('active');
        s.id2.setState('fail');
        s.ride(s.id2, s.paths.toDlq, p);
        if (p >= 1) {
          b.handle.setState('idle');
          s.dlq.setState('done');
        }
      }
    },
    {
      // BLPOP reaches the next list: conserver/main.py:875. Failed save: main.py:411
      // to :429, which logs and does not re-raise. _dead_letter_storage: main.py:436,
      // enqueue_storage_dlq at common/lib/queue.py:111, name at common/dlq_utils.py:7.
      id: 'failed-save-to-storage-dlq',
      label: 'A failed save fills the storage DLQ',
      caption: 'List A is empty, so the next BLPOP takes id 3 from list B. A failed save pushes the id onto the DLQ of that backend and raises nothing, so the id stays out of the ingress DLQ.',
      duration: 2400,
      draw: function (p, ctx) {
        var s = ctx.state;
        var a = s.workers[0];
        var pop = ctx.seg(p, 0, 0.3);
        var run = ctx.seg(p, 0.3, 0.45);
        var save = ctx.seg(p, 0.45, 0.7);
        var dead = ctx.seg(p, 0.7, 1);
        s.calm();
        ctx.show(s.body, false);
        if (pop > 0 && run <= 0) { a.wPop.on(); a.loop.setState('active'); }
        if (run > 0) { a.wSerial.on(); a.handle.setState('active'); }
        if (save > 0) {
          a.wSerial.off();
          a.wSave.on('fail');
          s.storage.setState('fail');
          s.body.setState('fail');
          s.body.setLabel('vCon');
          s.ride(s.body, s.paths.toSave, save);
        }
        if (dead > 0) {
          ctx.show(s.body, false);
          a.wSave.off();
          a.wSdlq.on('fail');
          s.sdlq.setState('active');
          s.id3.setState('fail');
        }
        s.ride(s.id3, s.paths.popB1, pop);
        s.ride(s.id3, s.paths.dispatch1, run);
        s.ride(s.id3, s.paths.toSdlq, dead);
        if (p >= 1) { s.sdlq.setState('done'); }
      }
    },
    {
      // Timeout: conserver/main.py:875 to :881. VconQueue.dequeue returns None on
      // timeout, common/lib/queue.py:88. The next pass rereads config at main.py:862.
      id: 'blpop-timeout',
      label: 'Empty lists time out the BLPOP',
      caption: 'With every list empty, BLPOP returns nothing after 15 s. The worker starts another pass and rereads the config.',
      duration: 1800,
      draw: function (p, ctx) {
        var s = ctx.state;
        s.calm();
        s.workers.forEach(function (w) {
          w.loop.setState('active');
          w.wPop.on();
        });
        ctx.setText(s.timer, p >= 1
          ? 'BLPOP returned nothing,\nnext pass'
          : 'BLPOP timeout\nin ' + Math.ceil(15 * (1 - p)) + ' s');
      }
    },
    {
      // RPOP: api/api.py:591. Replay: api/api.py:1168 (LPOP through
      // dequeue_dlq_async, common/lib/queue.py:163) and :1171 (RPUSH).
      // Storage replay: api/api.py:1230 (LRANGE), :1233 (save), :1239 (LREM).
      // Same list name: conserver/main.py:366 writes what main.py:875 reads.
      id: 'readers-drain-outputs',
      label: 'Readers drain the output lists',
      caption: 'GET /vcon/egress takes ids with RPOP, POST /dlq/reprocess moves ids back to their ingress list, and POST /dlq/storage/reprocess retries the save. An egress list named like an ingress list feeds that chain directly.',
      duration: 2600,
      draw: function (p, ctx) {
        var s = ctx.state;
        s.calm();
        ctx.setText(s.timer, '');
        s.reader.setState('active');
        s.replay.setState('active');
        s.sreplay.setState('active');
        s.wRead.on();
        s.wDlqOut.on();
        s.wReplay.on();
        s.wSdlqOut.on();
        s.wResave.on();
        s.wLoopback.on();
        s.id1.setState('done');
        s.id2.setState('idle');
        s.id3.setState('done');
        s.ride(s.id1, s.paths.read, ctx.seg(p, 0, 0.4));
        s.ride(s.id3, s.paths.resave, ctx.seg(p, 0, 0.8));
        s.ride(s.id2, s.paths.replayOut, p);
        if (p >= 1) {
          ctx.show(s.id1, false);
          s.storage.setState('done');
        }
      }
    },
    {
      // Health check: conserver/main.py:1012 (5 s sleep), :1015, restart at :1023 to
      // :1030 with the same worker_id. No in-flight record: BLPOP at :875 removes
      // the entry and nothing else records it.
      id: 'dead-worker-restart',
      label: 'The main process replaces a dead worker',
      caption: 'The main process checks every 5 s and restarts a dead worker under the same number. A popped id has no in-flight record, so the queue entry that worker held is gone.',
      duration: 2400,
      draw: function (p, ctx) {
        var s = ctx.state;
        var b = s.workers[1];
        var pop = ctx.seg(p, 0, 0.3);
        var dead = p >= 0.35;
        var back = p >= 0.75;
        s.calm();
        ctx.show(s.id3, false);
        b.frame.removeAttribute('stroke-dasharray');
        if (pop > 0 && !dead) { b.wPop.on(); b.loop.setState('active'); }
        s.ride(s.id2, s.paths.popA2, pop);
        if (dead) {
          s.id2.setState('fail');
          s.id2.setLabel('lost');
        }
        if (dead && !back) {
          b.loop.setState('fail');
          b.handle.setState('fail');
          b.pool.setState('fail');
          b.frame.setAttribute('stroke-dasharray', '6 4');
        }
        if (back) {
          s.main.setState('active');
          b.wSpawn.on();
          ctx.setText(b.title, 'Worker-2, new PID');
        }
      }
    },
    {
      // SIGTERM: conserver/main.py:98 to :102. LPUSH on a late pop: :890 to :899,
      // VconQueue.enqueue_front at common/lib/queue.py:71. Pool drain: :918 to :920.
      // Join and terminate: :1037 to :1042.
      id: 'shutdown-returns-id',
      label: 'Shutdown returns the popped id',
      caption: 'SIGTERM reaches every live worker. A worker that pops an id after the signal puts it back at the head with LPUSH, so the next worker sees it first. Thread pools drain, and the main process waits up to 30 s per worker before terminate.',
      duration: 2600,
      hold: 1200,
      draw: function (p, ctx) {
        var s = ctx.state;
        var a = s.workers[0];
        var push = ctx.seg(p, 0, 0.3);
        var pop = ctx.seg(p, 0.3, 0.55);
        var back = ctx.seg(p, 0.6, 0.95);
        s.calm();
        ctx.show(s.id2, false);
        s.main.setState('active');
        if (push > 0 && pop <= 0) { s.api.setState('active'); s.wApi.on(); }
        if (pop > 0 && back <= 0) { a.wPop.on(); a.loop.setState('active'); }
        if (back > 0) {
          a.wPush.on();
          s.workers.forEach(function (w) {
            w.wSpawn.on();
            if (w !== a) { w.loop.setState('muted'); }
            w.handle.setState('muted');
            w.pool.setState('muted');
          });
          a.loop.setState('active');
        }
        s.ride(s.id4, s.paths.apiIn, push);
        s.ride(s.id4, s.paths.popA1, pop);
        s.ride(s.id4, s.paths.giveBack, back);
        if (p >= 1) {
          s.wires.forEach(function (w) { w.off(); });
          s.main.setState('done');
          a.loop.setState('muted');
        }
      }
    }
  ]
});
