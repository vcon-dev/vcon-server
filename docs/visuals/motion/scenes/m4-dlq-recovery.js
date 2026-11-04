/* M4. A failed vCon reaches the DLQ and returns. Twins: D08, D09.

   One vCon id walks both dead letter paths. Each step comment names the code
   it draws. Line numbers are from this worktree, base commit 323109a.

   Left out on purpose, as in the twins or to keep one storyline:
   - Skipped by hook, halted by a link, shutdown LPUSH (D08 only).
   - A tracer with dlq_vcon_on_error, or an egress enqueue, can also raise into
     the ingress DLQ: conserver/main.py:545-546, conserver/main.py:361-366.
   - POST /dlq/storage/reprocess returns 404 for an unknown backend and 409 when
     the lock is held: api/api.py:1212-1216, api/api.py:1222-1223. D09 draws both.
   - HTTP 500 on a Redis error during replay: api/api.py:1242-1246.

   No vCon is built here. The tokens carry an id and nothing else. */
(function () {
  'use strict';

  var ROW = 110;          // top of the worker row
  var HOLD = 1500;        // reading time after a step
  var PARK = {
    ingress: [89, ROW],
    worker: [250, ROW],
    links: [406, ROW],
    wrap: [562, ROW],
    dlq: [466, 290],
    storageDlq: [800, 290],
    backendA: [880, 44],
    backendB: [880, 144]
  };

  // Moves a token from one parking spot, along an edge, to the next spot.
  function travel(ctx, token, edge, from, to, p) {
    var start = edge.pointAt(0);
    var end = edge.pointAt(1);
    if (p <= 0.12) {
      var a = ctx.seg(p, 0, 0.12);
      token.at(ctx.lerp(from[0], start[0], a), ctx.lerp(from[1], start[1], a));
    } else if (p < 0.85) {
      token.follow(edge, ctx.ease(ctx.seg(p, 0.12, 0.85)));
    } else {
      var c = ctx.seg(p, 0.85, 1);
      token.at(ctx.lerp(end[0], to[0], c), ctx.lerp(end[1], to[1], c));
    }
  }

  // Sets the panel that lists where this one id sits.
  function redis(ctx, values) {
    var r = ctx.state.redis;
    ['ingress', 'dlq', 'storageDlq', 'ttl'].forEach(function (key) {
      if (values[key] !== undefined) { ctx.setText(r[key], values[key]); }
    });
  }

  function exchange(ctx, request, response) {
    ctx.setText(ctx.state.request, request ? 'Request: ' + request : '');
    ctx.setText(ctx.state.response, response ? 'Response: ' + response : '');
  }

  // Runs the request card from the operator, through the API, to a target list.
  function call(ctx, label, target, p) {
    var s = ctx.state;
    var going = p < 1;
    s.t.request.setLabel(label);
    ctx.show(s.t.request, going);
    s.e.operatorApi.setState(going ? 'active' : 'idle');
    target.setState(going ? 'active' : 'idle');
    s.n.operator.setState('active');
    s.n.api.setState('active');
    if (p < 0.5) {
      s.t.request.follow(s.e.operatorApi, ctx.ease(ctx.seg(p, 0, 0.5)));
    } else {
      s.t.request.follow(target, ctx.ease(ctx.seg(p, 0.5, 1)));
    }
  }

  function operatorIdle(ctx) {
    ctx.state.n.operator.setState('idle');
    ctx.state.n.api.setState('idle');
  }

  VconMotion.register({
    id: 'm4',
    title: 'A failed vCon reaches the DLQ and returns',
    summary: 'One vCon id fails in a link and returns through the ingress DLQ, then fails a storage write and returns through the storage DLQ.',
    twins: ['D08-dead-letter-flow', 'D09-storage-write-recovery'],

    setup: function (ctx) {
      var s = ctx.state;
      var n = {
        ingress: ctx.node({ x: 24, y: ROW, w: 130, label: 'Ingress list', sub: '<ingress_list>' }),
        worker: ctx.node({ x: 190, y: ROW, w: 120, label: 'Worker', sub: 'BLPOP' }),
        links: ctx.node({ x: 346, y: ROW, w: 120, label: 'Links', sub: 'run in order' }),
        wrap: ctx.node({ x: 502, y: ROW, w: 120, label: 'Wrap-up', sub: 'egress, storage' }),
        egress: ctx.node({ x: 482, y: 16, w: 160, h: 52, label: 'Egress lists', sub: 'if the chain has any' }),
        backendA: ctx.node({ x: 770, y: 50, w: 160, h: 60, label: 'Backend A', sub: 'storage adapter' }),
        backendB: ctx.node({ x: 770, y: 150, w: 160, h: 60, label: 'Backend B', sub: 'storage adapter' }),
        dlq: ctx.node({ x: 306, y: 290, w: 200, label: 'Ingress DLQ', sub: 'DLQ:<ingress_list>' }),
        storageDlq: ctx.node({ x: 640, y: 290, w: 220, label: 'Storage DLQ', sub: 'DLQ:storage:<backend>' }),
        operator: ctx.node({ x: 24, y: 420, w: 130, label: 'Operator' }),
        api: ctx.node({ x: 326, y: 420, w: 160, label: 'API', sub: '/dlq routes' })
      };
      s.n = n;

      s.e = {
        ingressWorker: ctx.edge({ from: n.ingress.right, to: n.worker.left }),
        workerLinks: ctx.edge({ from: n.worker.right, to: n.links.left }),
        linksWrap: ctx.edge({ from: n.links.right, to: n.wrap.left }),
        wrapEgress: ctx.edge({ from: n.wrap.top, to: n.egress.bottom }),
        wrapA: ctx.edge({ from: [622, 130], via: [[700, 130], [700, 80]], to: n.backendA.left }),
        wrapB: ctx.edge({ from: [622, 154], via: [[700, 154], [700, 180]], to: n.backendB.left }),
        linksDlq: ctx.edge({ from: n.links.bottom, to: n.dlq.top }),
        wrapStorageDlq: ctx.edge({ from: n.wrap.bottom, via: [[562, 308]], to: [640, 308] }),
        dlqIngress: ctx.edge({ from: n.dlq.left, via: [[89, 322]], to: n.ingress.bottom, dashed: true }),
        storageDlqB: ctx.edge({ from: [850, 290], to: [850, 210], dashed: true }),
        operatorApi: ctx.edge({ from: n.operator.right, to: n.api.left }),
        apiDlq: ctx.edge({ from: n.api.top, to: n.dlq.bottom, dashed: true }),
        apiStorageDlq: ctx.edge({ from: n.api.right, via: [[600, 452], [600, 338]], to: [640, 338], dashed: true })
      };

      function edgeNote(x, y, text, anchor) {
        ctx.text({ x: x, y: y, text: text, kind: 'small', anchor: anchor, parent: ctx.layers.edges });
      }
      edgeNote(414, 236, 'link raises');
      edgeNote(570, 250, 'backend save raises');
      edgeNote(858, 254, 'write only');
      edgeNote(197, 314, 'POST /dlq/reprocess', 'middle');
      edgeNote(197, 340, 'LPOP, RPUSH, chain reruns', 'middle');

      // Panel with the position of this id, so state never rests on colour.
      ctx.el('rect', {
        x: 640, y: 392, width: 296, height: 128, rx: 4,
        fill: ctx.tokens.surface, stroke: ctx.tokens.muted
      }, ctx.layers.back);
      ctx.text({ x: 654, y: 416, text: 'Redis state for this id', kind: 'label' });
      function row(y, name, value) {
        ctx.text({ x: 654, y: y, text: name, kind: 'small' });
        return ctx.text({ x: 922, y: y, text: value, kind: 'small', anchor: 'end' });
      }
      s.redis = {
        ingress: row(442, 'Ingress list', '1 id'),
        dlq: row(464, 'DLQ:<ingress_list>', 'empty'),
        storageDlq: row(486, 'DLQ:storage:<backend>', 'empty'),
        // api/api.py:789 and :893 cache the body with this TTL, api/api.py:450-452.
        // Link writes keep the TTL: common/lib/vcon_redis.py:108, common/redis_mgr.py:56-57.
        ttl: row(508, 'Body TTL', 'VCON_REDIS_EXPIRY')
      };

      s.lock = ctx.text({ x: 750, y: 372, text: '', kind: 'small', anchor: 'middle' });
      s.request = ctx.text({ x: 24, y: 508, text: '' });
      s.response = ctx.text({ x: 24, y: 528, text: '' });

      s.t = {
        id: ctx.token({ x: PARK.ingress[0], y: PARK.ingress[1], label: 'vCon id' }),
        egress: ctx.token({ label: 'vCon id', hidden: true }),
        backendA: ctx.token({ label: 'vCon id', hidden: true }),
        retry: ctx.token({ label: 'vCon id', hidden: true }),
        request: ctx.token({ label: 'POST', w: 56, hidden: true })
      };

      n.ingress.setState('active');
    },

    steps: [
      {
        // conserver/main.py:875 queue.dequeue, common/lib/queue.py:81-90 BLPOP.
        // common/lib/queue.py:41-42 builds the body key vcon:<uuid>.
        id: 'pop',
        label: 'A worker pops the id',
        caption: 'A worker takes the vCon id from the head of the ingress list with BLPOP. Lists hold ids only, and the body stays at vcon:<uuid>.',
        duration: 1400,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          s.e.ingressWorker.setState(p < 1 ? 'active' : 'idle');
          travel(ctx, s.t.id, s.e.ingressWorker, PARK.ingress, PARK.worker, p);
          if (p >= 1) {
            s.n.ingress.setState('idle');
            s.n.worker.setState('active');
            redis(ctx, { ingress: 'empty' });
          }
        }
      },
      {
        // conserver/main.py:255-263 runs the links in order.
        // conserver/main.py:646-670 _process_link logs and re-raises.
        // conserver/main.py:754 _handle_vcon catches it.
        id: 'link-raises',
        label: 'A link raises an exception',
        caption: 'A link raises, so the chain stops and the later links never run. The worker catches the exception in _handle_vcon.',
        duration: 1400,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          s.e.workerLinks.setState(p < 1 ? 'active' : 'idle');
          travel(ctx, s.t.id, s.e.workerLinks, PARK.worker, PARK.links, p);
          if (p >= 1) {
            s.n.worker.setState('idle');
            s.n.links.setState('fail');
            s.n.links.setLabel('Links', 'link raised');
            s.t.id.setState('fail');
          }
        }
      },
      {
        // conserver/main.py:761 enqueue_dlq, common/lib/queue.py:92-109 RPUSH and
        // conserver.dlq.count, common/dlq_utils.py:3-4 the name.
        // conserver/main.py:762-763 EXPIRE when VCON_DLQ_EXPIRY > 0, plain EXPIRE
        // at common/lib/queue.py:143-145, default at common/settings.py:56.
        id: 'ingress-dlq',
        label: 'The id lands on the ingress DLQ',
        caption: 'The worker pushes the id onto DLQ:<ingress_list> with RPUSH. It then resets the body TTL to VCON_DLQ_EXPIRY, 604800 seconds by default, unless that setting is 0.',
        duration: 1400,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          s.e.linksDlq.setState(p < 1 ? 'fail' : 'idle');
          travel(ctx, s.t.id, s.e.linksDlq, PARK.links, PARK.dlq, p);
          if (p >= 1) {
            s.n.links.setState('idle');
            s.n.links.setLabel('Links', 'run in order');
            s.n.dlq.setState('active');
            redis(ctx, { dlq: '1 id', ttl: 'VCON_DLQ_EXPIRY' });
          }
        }
      },
      {
        // api/api.py:1269-1296 GET /dlq, LRANGE 0 -1, no write.
        id: 'ingress-read',
        label: 'The operator reads the ingress DLQ',
        caption: 'GET /dlq returns the waiting ids with LRANGE. The call only reads, so the list keeps every id.',
        duration: 1200,
        hold: HOLD,
        draw: function (p, ctx) {
          call(ctx, 'GET', ctx.state.e.apiDlq, p);
          exchange(ctx, 'GET /dlq?ingress_list=<name>', p >= 1 ? '200, JSON list of ids' : '');
        }
      },
      {
        // api/api.py:1142-1182 POST /dlq/reprocess, count from 1 to 100000, default
        // 1000. api/api.py:1168 dequeue_dlq_async is LPOP, common/lib/queue.py:163-173.
        // api/api.py:1171 enqueue_async is RPUSH, common/lib/queue.py:149-158.
        // These are two commands per id, not one atomic step. Returns the count moved.
        id: 'ingress-replay',
        label: 'The operator replays the ingress DLQ',
        caption: 'POST /dlq/reprocess moves up to count ids, 1000 by default, with LPOP then RPUSH. The id joins the tail of its ingress list.',
        duration: 2000,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          call(ctx, 'POST', s.e.apiDlq, ctx.seg(p, 0, 0.45));
          exchange(ctx, 'POST /dlq/reprocess?ingress_list=<name>&count=N', p >= 1 ? '200 with the number moved, 1' : '');
          s.e.dlqIngress.setState(p > 0.45 && p < 1 ? 'active' : 'idle');
          if (p > 0.45) {
            s.t.id.setState('idle');
            travel(ctx, s.t.id, s.e.dlqIngress, PARK.dlq, PARK.ingress, ctx.seg(p, 0.45, 1));
          }
          if (p >= 1) {
            s.n.dlq.setState('idle');
            s.n.ingress.setState('active');
            redis(ctx, { ingress: '1 id', dlq: 'empty' });
          }
        }
      },
      {
        // conserver/main.py:875 pops again. conserver/main.py:255 loops from link 0.
        // conserver/main.py:273-274 reaches _wrap_up when every link returned an id.
        // A link that still raises sends the id back to the ingress DLQ.
        id: 'chain-reruns',
        label: 'A worker reruns the whole chain',
        caption: 'A worker pops the id again and every link runs from the first one. Each link returns the id this time, so the worker reaches wrap-up.',
        duration: 2400,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          operatorIdle(ctx);
          exchange(ctx, '', '');
          s.n.ingress.setState(p < 0.33 ? 'active' : 'idle');
          s.n.worker.setState(p >= 0.33 && p < 0.66 ? 'active' : 'idle');
          s.n.links.setState(p >= 0.66 && p < 1 ? 'active' : 'idle');
          s.e.ingressWorker.setState(p < 0.33 ? 'active' : 'idle');
          s.e.workerLinks.setState(p >= 0.33 && p < 0.66 ? 'active' : 'idle');
          s.e.linksWrap.setState(p >= 0.66 && p < 1 ? 'active' : 'idle');
          if (p < 0.33) {
            travel(ctx, s.t.id, s.e.ingressWorker, PARK.ingress, PARK.worker, ctx.seg(p, 0, 0.33));
          } else if (p < 0.66) {
            travel(ctx, s.t.id, s.e.workerLinks, PARK.worker, PARK.links, ctx.seg(p, 0.33, 0.66));
          } else {
            travel(ctx, s.t.id, s.e.linksWrap, PARK.links, PARK.wrap, ctx.seg(p, 0.66, 1));
          }
          if (p >= 0.33) { redis(ctx, { ingress: 'empty' }); }
          if (p >= 1) { s.n.wrap.setState('active'); }
        }
      },
      {
        // conserver/main.py:352-366 egress RPUSH, storage starts at conserver/main.py:368.
        id: 'egress',
        label: 'Wrap-up feeds the egress lists',
        caption: 'Wrap-up pushes the id onto any egress lists in the chain first. Storage writes start only after that.',
        duration: 1100,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          s.e.wrapEgress.setState(p < 1 ? 'active' : 'idle');
          ctx.show(s.t.egress, p < 1);
          s.t.egress.follow(s.e.wrapEgress, ctx.ease(p));
          if (p >= 1) {
            s.n.egress.setState('done');
            s.n.egress.setLabel('Egress lists', 'id pushed');
          }
        }
      },
      {
        // conserver/main.py:376-382 threads when parallel storage is on and there
        // are two or more backends, common/config.py:24, default at common/settings.py:66.
        // conserver/main.py:410 Storage(name).save, common/storage/base.py:63-65.
        // conserver/main.py:411 catches the exception, outcome=error at :412.
        id: 'backends',
        label: 'One backend rejects the write',
        caption: 'Each backend gets its own save, in parallel by default when the chain has two or more. Backend A returns and Backend B raises.',
        duration: 1800,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          var out = ctx.seg(p, 0, 0.6);
          var bounce = ctx.seg(p, 0.6, 1);
          ctx.show(s.t.backendA, true);
          s.e.wrapA.setState(p < 0.6 ? 'active' : 'idle');
          s.e.wrapB.setState(p < 0.6 ? 'active' : (p < 1 ? 'fail' : 'idle'));
          travel(ctx, s.t.backendA, s.e.wrapA, PARK.wrap, PARK.backendA, out);
          if (p < 0.6) {
            s.t.id.follow(s.e.wrapB, ctx.ease(out));
          } else {
            s.t.id.follow(s.e.wrapB, 1 - ctx.ease(bounce));
          }
          if (p >= 0.6) {
            s.t.backendA.setState('done');
            s.n.backendA.setState('done');
            s.n.backendA.setLabel('Backend A', 'saved');
            s.n.backendB.setState('fail');
            s.n.backendB.setLabel('Backend B', 'write raised');
            s.t.id.setState('fail');
          }
          if (p >= 1) { s.t.id.at(PARK.wrap[0], PARK.wrap[1]); }
        }
      },
      {
        // conserver/main.py:429 _dead_letter_storage, conserver/main.py:446-449.
        // common/lib/queue.py:121-132 one EVAL: TTL -2 returns -1, else EXPIRE only
        // when retention > 0 and 0 <= ttl < retention, then RPUSH. The TTL row stays
        // VCON_DLQ_EXPIRY because this id already carries that setting.
        // common/lib/queue.py:133-134 ValueError on -1, conserver/main.py:450-456
        // logs manual recovery and never re-raises.
        // conserver/main.py:425-429 is why the ingress DLQ stays out of this.
        id: 'storage-dlq',
        label: 'The id lands on the storage DLQ',
        caption: 'One atomic script raises a TTL below VCON_DLQ_EXPIRY and pushes the id onto DLQ:storage:<backend>, or the worker logs for manual recovery when the body is gone. Nothing re-raises, so the chain does not rerun.',
        duration: 1500,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          s.e.wrapStorageDlq.setState(p < 1 ? 'fail' : 'idle');
          travel(ctx, s.t.id, s.e.wrapStorageDlq, PARK.wrap, PARK.storageDlq, p);
          if (p >= 1) {
            s.n.wrap.setState('idle');
            s.n.storageDlq.setState('active');
            redis(ctx, { storageDlq: '1 id' });
          }
        }
      },
      {
        // api/api.py:1185-1202 POST /dlq/storage/reprocess, api/api.py:1221 lock with
        // no expiry, api/api.py:1230 LRANGE snapshot, api/api.py:1233 save in the
        // threadpool, api/api.py:1234-1238 warning then break, api/api.py:1241 returns
        // the count, api/api.py:1245-1246 releases the lock.
        id: 'retry-fails',
        label: 'The backend refuses the first retry',
        caption: 'POST /dlq/storage/reprocess takes the replay lock, snapshots ids with LRANGE and calls save. The save raises, so the batch stops, the id stays on the list and the response is 200 with 0.',
        duration: 2400,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          var out = ctx.seg(p, 0.4, 0.75);
          call(ctx, 'POST', s.e.apiStorageDlq, ctx.seg(p, 0, 0.4));
          exchange(ctx, 'POST /dlq/storage/reprocess?storage_name=<name>&count=N', p >= 1 ? '200 with the number written, 0' : '');
          if (p >= 0.4) { ctx.setText(s.lock, p >= 1 ? 'Replay lock released' : 'Replay lock held'); }
          s.e.storageDlqB.setState(p > 0.4 && p < 0.75 ? 'active' : (p >= 0.75 && p < 1 ? 'fail' : 'idle'));
          ctx.show(s.t.retry, p > 0.4 && p < 1);
          s.t.retry.setState(p >= 0.75 ? 'fail' : 'idle');
          s.t.retry.follow(s.e.storageDlqB, p < 0.75 ? ctx.ease(out) : 1 - ctx.ease(ctx.seg(p, 0.75, 1)));
          s.n.backendB.setLabel('Backend B', p >= 0.75 ? 'retry raised' : 'write raised');
        }
      },
      {
        // Same route as the step before. api/api.py:1233 save returns,
        // api/api.py:1239-1240 LREM one entry, api/api.py:1241 returns the count.
        // Replay is at-least-once, api/api.py:1227-1229.
        id: 'retry-succeeds',
        label: 'A second retry clears the entry',
        caption: 'The backend is healthy again, so save returns and LREM removes the id. Only the write ran, not the chain, and the response is 200 with 1.',
        duration: 2200,
        hold: HOLD,
        draw: function (p, ctx) {
          var s = ctx.state;
          call(ctx, 'POST', s.e.apiStorageDlq, ctx.seg(p, 0, 0.4));
          exchange(ctx, 'POST /dlq/storage/reprocess?storage_name=<name>&count=N', p >= 1 ? '200 with the number written, 1' : '');
          if (p >= 0.4) { ctx.setText(s.lock, p >= 1 ? 'Replay lock released' : 'Replay lock held'); }
          s.e.storageDlqB.setState(p > 0.4 && p < 1 ? 'active' : 'idle');
          if (p > 0.4) {
            s.t.id.setState('idle');
            travel(ctx, s.t.id, s.e.storageDlqB, PARK.storageDlq, PARK.backendB, ctx.seg(p, 0.4, 1));
          }
          if (p >= 1) {
            operatorIdle(ctx);
            s.t.id.setState('done');
            s.n.storageDlq.setState('idle');
            s.n.backendB.setState('done');
            s.n.backendB.setLabel('Backend B', 'saved');
            redis(ctx, { storageDlq: 'empty' });
          }
        }
      }
    ]
  });
}());
