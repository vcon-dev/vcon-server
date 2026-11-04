/* M1: a vCon runs a chain. Twin of D01-system-context and D05-chain-pipeline.
   Paths and line numbers point at the code each step draws, in this worktree.
   Every draw paints the whole frame through paint(), so draw(1, ctx) alone
   gives the full end state of a step, as the scene-authoring.md contract requires. */
(function () {
  'use strict';

  var COL = [25, 265, 505, 745];  // four columns of 190 wide boxes
  var W = 190;
  var ROW = { a: 30, b: 140, c: 276, d: 410 };

  var MAIN_NODES = ['api', 'ingress', 'worker', 'before', 'link1', 'link2', 'egress', 'mode', 'save', 'after'];
  var EXIT_NODES = ['skipped', 'halted', 'routed', 'dlq', 'sdlq'];
  var MAIN_EDGES = ['apiIngress', 'ingressWorker', 'workerBefore', 'beforeLink', 'linkLink', 'linkEgress', 'egressMode', 'modeSave', 'saveAfter'];
  var EXIT_EDGES = ['beforeSkipped', 'skippedAfter', 'linkHalted', 'haltedAfter', 'linkRouted', 'linkDlq', 'beforeDlq', 'dlqAfter', 'saveSdlq', 'sdlqAfter'];

  var LINK_LABELS = {
    link1: ['Link 1', 'module.run(...)'],
    link2: ['Link 2', 'module.run(...)']
  };

  function has(list, name) { return (list || []).indexOf(name) !== -1; }

  // Sets every node and edge from one spec. base is the state of main path
  // items the spec does not name. Exit nodes rest as muted, exit edges hidden.
  function paint(ctx, spec) {
    var s = ctx.state;
    var base = spec.base || 'idle';

    function nodeState(name, fallback) {
      if (has(spec.fail, name)) { return 'fail'; }
      if (has(spec.active, name)) { return 'active'; }
      if (has(spec.done, name)) { return 'done'; }
      return fallback;
    }

    MAIN_NODES.forEach(function (name) { s.n[name].setState(nodeState(name, base)); });
    EXIT_NODES.forEach(function (name) { s.n[name].setState(nodeState(name, 'muted')); });

    MAIN_EDGES.forEach(function (name) {
      s.e[name].setState(has(spec.edges, name) ? 'active' : base);
    });
    EXIT_EDGES.forEach(function (name) {
      var failed = has(spec.failEdges, name);
      ctx.show(s.e[name], failed || has(spec.edges, name));
      s.e[name].setState(failed ? 'fail' : 'active');
    });

    Object.keys(LINK_LABELS).forEach(function (name) {
      var label = (spec.labels && spec.labels[name]) || LINK_LABELS[name];
      s.n[name].setLabel(label[0], label[1]);
    });

    s.token.setLabel(spec.tokenLabel || 'vCon id');
    s.token.setState(spec.tokenState || 'idle');
    ctx.show(s.copy, false);
  }

  // A hidden polyline for the token to follow. Tokens rest on the top edge of
  // a box, so the route leaves and rejoins that spot and the label stays clear.
  function route(ctx, points) {
    var line = ctx.edge({
      from: points[0],
      to: points[points.length - 1],
      via: points.slice(1, -1)
    });
    ctx.show(line, false);
    return line;
  }

  VconMotion.register({
    id: 'm1',
    title: 'A vCon runs a chain',
    summary: 'A vCon id leaves the API, passes through a worker, two links, egress and storage, and then takes each of the other exits a chain can reach.',
    twins: ['D01-system-context', 'D05-chain-pipeline'],

    setup: function (ctx) {
      var s = ctx.state;

      // Back panels, matching the _wrap_up subgraph in D05.
      var panel = { rx: 6, fill: ctx.tokens.white, stroke: ctx.tokens.muted, 'stroke-width': 1 };
      ctx.el('rect', Object.assign({ x: 14, y: 128, width: 452, height: 108 }, panel), ctx.layers.back);
      ctx.el('rect', Object.assign({ x: 14, y: 264, width: 930, height: 108 }, panel), ctx.layers.back);
      ctx.text({ x: 26, y: 226, text: 'Links, in order', kind: 'small', parent: ctx.layers.back });
      ctx.text({ x: 26, y: 362, text: '_wrap_up, in this order', kind: 'small', parent: ctx.layers.back });

      function box(col, row, label, sub) {
        return ctx.node({ x: COL[col], y: ROW[row], w: W, h: 64, label: label, sub: sub });
      }

      var n = s.n = {
        api: box(0, 'a', 'api service', 'FastAPI, port 8000'),
        ingress: box(1, 'a', 'Ingress list', 'Redis list of vCon ids'),
        worker: box(2, 'a', 'worker_loop', 'pops one id, finds the chain'),
        before: box(3, 'a', 'hook.before_processing', 'returns truthy?'),
        link1: box(0, 'b', LINK_LABELS.link1[0], LINK_LABELS.link1[1]),
        link2: box(1, 'b', LINK_LABELS.link2[0], LINK_LABELS.link2[1]),
        halted: box(2, 'b', 'Chain halted', 'no storage or egress'),
        skipped: box(3, 'b', 'vCon skipped', 'no links, storage or egress'),
        egress: box(0, 'c', 'Egress lists', 'trace context stored first'),
        mode: box(1, 'c', 'Parallel storage?', 'on, and 2 or more backends'),
        save: box(2, 'c', 'Storage(name).save', 'one call per backend'),
        sdlq: box(3, 'c', 'DLQ:storage:backend', 'body TTL extended'),
        routed: box(0, 'd', 'Another Redis list', 'tag_router only'),
        dlq: box(2, 'd', 'DLQ:ingress_list', 'TTL set to VCON_DLQ_EXPIRY'),
        after: box(3, 'd', 'hook.after_processing', 'runs on every path')
      };

      function rest(node) { return [node.cx, node.y]; }

      var bottomA = ROW.a + 64;
      var linkY = n.link1.cy;
      var d = n.dlq.cy;

      var P = {
        truthyOut: [800, bottomA],
        falsyOut: [880, bottomA],
        skippedIn: [880, n.skipped.y],
        raiseOut: [770, bottomA],
        linkRaise: [n.link2.x + W, linkY + 18],
        haltedIn: [n.after.x, d - 14],
        dlqIn: [n.dlq.x + W, d - 14],
        dlqOut: [n.dlq.x + W, d + 14],
        afterDlq: [n.after.x, d + 14],
        saveIn: [800, n.after.y],
        sdlqOut: [880, n.sdlq.y + 64],
        sdlqIn: [880, n.after.y]
      };
      var V = {
        truthy: [[800, 116], [120, 116]],
        wrapUp: [[n.link2.cx, 255], [n.egress.cx, 255]],
        saved: [[n.save.cx, 392], [800, 392]],
        skip: [[951, linkY], [951, d]],
        halt: [[720, linkY], [720, d - 14]],
        tag: [[9, linkY], [9, d]],
        linkRaise: [[480, linkY + 18], [480, d]],
        hookRaise: [[770, 106], [732, 106], [732, d - 14]]
      };

      s.e = {
        apiIngress: ctx.edge({ from: n.api.right, to: n.ingress.left }),
        ingressWorker: ctx.edge({ from: n.ingress.right, to: n.worker.left }),
        workerBefore: ctx.edge({ from: n.worker.right, to: n.before.left }),
        beforeLink: ctx.edge({ from: P.truthyOut, via: V.truthy, to: n.link1.top, label: 'truthy' }),
        linkLink: ctx.edge({ from: n.link1.right, to: n.link2.left, label: 'same id' }),
        linkEgress: ctx.edge({ from: n.link2.bottom, via: V.wrapUp, to: n.egress.top, label: 'no more links' }),
        egressMode: ctx.edge({ from: n.egress.right, to: n.mode.left }),
        modeSave: ctx.edge({ from: n.mode.right, to: n.save.left }),
        saveAfter: ctx.edge({ from: n.save.bottom, via: V.saved, to: P.saveIn, label: 'ok' }),

        beforeSkipped: ctx.edge({ from: P.falsyOut, to: P.skippedIn }),
        skippedAfter: ctx.edge({ from: n.skipped.right, via: V.skip, to: n.after.right }),
        linkHalted: ctx.edge({ from: n.link2.right, to: n.halted.left, label: 'falsy' }),
        haltedAfter: ctx.edge({ from: n.halted.right, via: V.halt, to: P.haltedIn }),
        linkRouted: ctx.edge({ from: n.link1.left, via: V.tag, to: n.routed.left, dashed: true }),
        linkDlq: ctx.edge({ from: P.linkRaise, via: V.linkRaise, to: n.dlq.left }),
        beforeDlq: ctx.edge({ from: P.raiseOut, via: V.hookRaise, to: P.dlqIn }),
        dlqAfter: ctx.edge({ from: P.dlqOut, to: P.afterDlq }),
        saveSdlq: ctx.edge({ from: n.save.right, to: n.sdlq.left, label: 'raises' }),
        sdlqAfter: ctx.edge({ from: P.sdlqOut, to: P.sdlqIn })
      };

      // Edge labels that the midpoint rule would place badly. Kept inside the
      // edge group so they hide and show with the edge.
      ctx.text({ x: 888, y: 122, text: 'falsy', parent: s.e.beforeSkipped.g });
      ctx.text({ x: 474, y: 392, text: 'raises', anchor: 'end', parent: s.e.linkDlq.g });
      ctx.text({ x: 726, y: 250, text: 'raises', anchor: 'end', parent: s.e.beforeDlq.g });

      function trip(from, points, to) {
        return route(ctx, [rest(from)].concat(points, [rest(to)]));
      }

      s.r = {
        toIngress: trip(n.api, [n.api.right, n.ingress.left], n.ingress),
        toWorker: trip(n.ingress, [n.ingress.right, n.worker.left], n.worker),
        toBefore: trip(n.worker, [n.worker.right, n.before.left], n.before),
        toLink1: trip(n.before, [P.truthyOut].concat(V.truthy), n.link1),
        toLink2: trip(n.link1, [n.link1.right, n.link2.left], n.link2),
        toEgress: trip(n.link2, [n.link2.bottom].concat(V.wrapUp), n.egress),
        toSave: trip(n.egress, [n.egress.right, n.mode.left, n.mode.right, n.save.left], n.save),
        toAfter: trip(n.save, [n.save.bottom].concat(V.saved), n.after),
        tag: trip(n.link1, [n.link1.left].concat(V.tag, [n.routed.left]), n.routed),
        skip: trip(n.before, [P.falsyOut, P.skippedIn, n.skipped.right].concat(V.skip, [n.after.right]), n.after),
        halt: trip(n.link2, [n.link2.right, n.halted.left, n.halted.right].concat(V.halt, [P.haltedIn]), n.after),
        raise: trip(n.link2, [P.linkRaise].concat(V.linkRaise, [n.dlq.left, n.dlq.right, P.dlqOut, P.afterDlq]), n.after),
        storeFail: trip(n.save, [n.save.right, n.sdlq.left, P.sdlqOut, P.sdlqIn], n.after)
      };

      s.token = ctx.token({ x: n.api.cx, y: n.api.y, label: 'vCon id', w: 74 });
      s.copy = ctx.token({ x: n.link1.cx, y: n.link1.y, label: 'vCon id', w: 74, hidden: true });

      ctx.text({
        x: 25,
        y: 508,
        kind: 'small',
        text: 'The token carries the id. The vCon body stays in Redis under vcon:<id>, where links read and write it.'
      });

      paint(ctx, { active: ['api'] });
    },

    steps: [
      {
        // api/api.py:758 post_vcon, :789 cache_vcon_in_redis, :806 queue.enqueue_async
        // common/lib/queue.py VconQueue. D01 edge "store vCons, RPUSH ingress lists".
        id: 'enqueue',
        label: 'The API queues the id',
        caption: 'POST /vcon stores the vCon in Redis. When the request names ingress lists, the API pushes the id onto each one.',
        duration: 1300,
        hold: 2000,
        draw: function (p, ctx) {
          paint(ctx, { done: ['api'], active: ['ingress'], edges: ['apiIngress'] });
          ctx.state.token.follow(ctx.state.r.toIngress, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:862 get_config, :865 get_ingress_chain_map,
        // :875 queue.dequeue (common/lib/queue.py:81 BLPOP), :901 chain lookup,
        // :905 _handle_vcon.
        id: 'pop',
        label: 'A worker pops the id',
        caption: 'worker_loop reloads the config, then waits on every ingress list with BLPOP. It finds the chain mapped to the list that gave it the id.',
        duration: 1300,
        hold: 2200,
        draw: function (p, ctx) {
          paint(ctx, { done: ['api', 'ingress'], active: ['worker'], edges: ['ingressWorker'] });
          ctx.state.token.follow(ctx.state.r.toWorker, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:747 inside _handle_vcon. conserver/hook.py:11, the
        // default returns the id. The docstring there says a Docker build may
        // replace hook.py.
        id: 'before-hook',
        label: 'The before hook passes the vCon',
        caption: 'hook.before_processing runs first. The default hook returns the id, and a truthy return lets the chain start.',
        duration: 1200,
        hold: 2000,
        draw: function (p, ctx) {
          paint(ctx, { done: ['api', 'ingress', 'worker'], active: ['before'], edges: ['workerBefore'] });
          ctx.state.token.follow(ctx.state.r.toBefore, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:255 loop, :256 _process_link, :603 module.run,
        // :264 same id leaves self.vcon_id alone. D01 edge "links call out".
        id: 'link-same-id',
        label: 'Link 1 returns the same id',
        caption: 'VconChainRequest.process calls module.run(vcon_id, link_name, options) for each link in turn. A link may call an outside service. The same id comes back, so the chain moves on.',
        duration: 1500,
        hold: 2600,
        draw: function (p, ctx) {
          paint(ctx, {
            done: ['api', 'ingress', 'worker', 'before'],
            active: ['link1'],
            edges: ['beforeLink'],
            labels: { link1: ['Link 1', 'returns the same id'] }
          });
          ctx.state.token.follow(ctx.state.r.toLink1, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:264 to :271, self.vcon_id takes the returned value.
        // A search of the run() returns in conserver/links found no bundled link
        // that returns a different id, so the caption states the contract only.
        id: 'link-new-id',
        label: 'Link 2 returns a new id',
        caption: 'A link may return a different id. The chain then carries that id forward through later links, egress and storage. A later exception still dead-letters the id the worker popped.',
        duration: 1300,
        hold: 2200,
        draw: function (p, ctx) {
          paint(ctx, {
            done: ['api', 'ingress', 'worker', 'before', 'link1'],
            active: ['link2'],
            edges: ['linkLink'],
            labels: {
              link1: ['Link 1', 'returns the same id'],
              link2: ['Link 2', 'returns a new id']
            },
            tokenLabel: p >= 1 ? 'new id' : 'vCon id'
          });
          ctx.state.token.follow(ctx.state.r.toLink2, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:273 _wrap_up, :352 egress_lists, :365 store_context_sync
        // when a context exists, :366 queue.enqueue. Egress runs before storage.
        id: 'egress',
        label: '_wrap_up pushes the egress lists',
        caption: 'With no links left, _wrap_up runs. It pushes the id onto each egress list before any storage write, so a downstream chain can start before the save ends. Trace context, when present, is stored before each push.',
        duration: 1400,
        hold: 2800,
        draw: function (p, ctx) {
          paint(ctx, {
            done: ['api', 'ingress', 'worker', 'before', 'link1', 'link2'],
            active: ['egress'],
            edges: ['linkEgress'],
            tokenLabel: 'new id'
          });
          ctx.state.token.follow(ctx.state.r.toEgress, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:376 mode check (common/settings.py:66 default true),
        // :378 and :475 thread per backend, :381 one at a time,
        // :410 Storage(name).save, common/storage/base.py:64.
        id: 'storage',
        label: '_wrap_up saves to each backend',
        caption: 'With CONSERVER_PARALLEL_STORAGE on, the default, and 2 or more backends, each backend gets its own thread. Otherwise writes run one at a time. Storage(name).save(vcon_id) calls the adapter.',
        duration: 1600,
        hold: 2800,
        draw: function (p, ctx) {
          paint(ctx, {
            done: ['api', 'ingress', 'worker', 'before', 'link1', 'link2', 'egress', 'mode'],
            active: ['save'],
            edges: ['egressMode', 'modeSave'],
            tokenLabel: 'new id'
          });
          ctx.state.token.follow(ctx.state.r.toSave, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:764 finally, :766 hook.after_processing with the
        // chain's current id. conserver/hook.py:31, the default does nothing.
        id: 'after-hook',
        label: 'The after hook closes the run',
        caption: 'hook.after_processing sits in a finally block and gets the current id. The default hook does nothing. The next steps show the other exits, and each one ends here too.',
        duration: 1300,
        hold: 2600,
        draw: function (p, ctx) {
          paint(ctx, {
            done: MAIN_NODES,
            edges: ['saveAfter'],
            tokenLabel: 'new id',
            tokenState: p >= 1 ? 'done' : 'idle'
          });
          ctx.state.token.follow(ctx.state.r.toAfter, ctx.ease(p));
        }
      },
      {
        // conserver/links/tag_router/__init__.py:88 queue.enqueue, :14 default
        // forward_original True, final return. It is the only link module that
        // pushes to a list, by grep for enqueue, rpush and lpush in conserver/links.
        id: 'tag-router',
        label: 'tag_router copies the id to another list',
        caption: 'tag_router pushes the id onto a list chosen by the tags on the vCon. With forward_original on, the default, it also returns the id and the chain goes on. With it off, the chain halts.',
        duration: 1400,
        hold: 2800,
        draw: function (p, ctx) {
          var s = ctx.state;
          paint(ctx, {
            base: 'muted',
            active: ['link1', 'routed'],
            edges: ['linkRouted'],
            labels: { link1: ['tag_router', 'queue.enqueue(list, id)'] }
          });
          s.token.at(s.n.link1.cx, s.n.link1.y);
          ctx.show(s.copy, true);
          s.copy.follow(s.r.tag, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:747 to :752, return with no chain run. :764 finally.
        // conserver/hook.py docstring: falsy skips without the DLQ.
        id: 'exit-skip',
        label: 'A falsy before hook skips the vCon',
        caption: 'A falsy return from hook.before_processing skips this vCon. No links, storage or egress run, and it goes to no DLQ.',
        duration: 1500,
        hold: 2200,
        draw: function (p, ctx) {
          paint(ctx, {
            base: 'muted',
            active: ['before', 'skipped', 'after'],
            edges: ['beforeSkipped', 'skippedAfter'],
            labels: {},
            tokenState: p >= 1 ? 'done' : 'idle'
          });
          ctx.state.token.follow(ctx.state.r.skip, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:257 to :263 break, :273 _wrap_up is skipped.
        // :288 a halted vCon still counts as processed.
        id: 'exit-halt',
        label: 'A falsy link return halts the chain',
        caption: 'A falsy return stops the loop and _wrap_up never runs, so this vCon gets no egress and no storage write. It is not an error and no DLQ is involved.',
        duration: 1500,
        hold: 2400,
        draw: function (p, ctx) {
          paint(ctx, {
            base: 'muted',
            active: ['link2', 'halted', 'after'],
            edges: ['linkHalted', 'haltedAfter'],
            labels: { link2: ['Link 2', 'returns falsy'] },
            tokenState: p >= 1 ? 'done' : 'idle'
          });
          ctx.state.token.follow(ctx.state.r.halt, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:670 re-raise, :754 except, :761 queue.enqueue_dlq,
        // :762 and :763 TTL when VCON_DLQ_EXPIRY is above 0, :770 error argument.
        // common/dlq_utils.py:3 builds DLQ:<ingress_list>. M4 follows the replay.
        id: 'exit-raise',
        label: 'An exception reaches the ingress DLQ',
        caption: 'An exception from a link or the before hook lands in _handle_vcon. It pushes the id onto DLQ:<ingress list> and sets the body TTL to VCON_DLQ_EXPIRY when that is above 0. hook.after_processing receives the error.',
        duration: 1600,
        hold: 2800,
        draw: function (p, ctx) {
          paint(ctx, {
            base: 'muted',
            active: ['after'],
            fail: ['link2', 'dlq'],
            failEdges: ['linkDlq', 'beforeDlq', 'dlqAfter'],
            labels: { link2: ['Link 2', 'raises'] },
            tokenState: 'fail'
          });
          ctx.state.token.follow(ctx.state.r.raise, ctx.ease(p));
        }
      },
      {
        // conserver/main.py:411 except, :425 comment, :429 _dead_letter_storage,
        // :447 queue.enqueue_storage_dlq, common/lib/queue.py:111,
        // common/dlq_utils.py:7 builds DLQ:storage:<backend>.
        id: 'exit-storage',
        label: 'A failed save reaches the storage DLQ',
        caption: 'A failed save does not fail the chain. _process_storage pushes the id onto DLQ:storage:<backend> and extends the body TTL, so a replay repeats only that write. Other backends still run, and hook.after_processing receives no error.',
        duration: 1600,
        hold: 2800,
        draw: function (p, ctx) {
          paint(ctx, {
            base: 'muted',
            active: ['after'],
            fail: ['save', 'sdlq'],
            failEdges: ['saveSdlq', 'sdlqAfter'],
            labels: {},
            tokenState: 'fail'
          });
          ctx.state.token.follow(ctx.state.r.storeFail, ctx.ease(p));
        }
      }
    ]
  });
}());
