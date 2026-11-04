/* M3: a vCon gains analysis, tags and attachments. Twins D07 and D10.

   The lane across the top uses the D07 states on the path a vCon takes through
   a successful chain. The card below uses the D10 parts of the Vcon class in
   common/vcon.py. Halts and DLQ paths belong to M1 and M4.

   The chain is an example: links.transcribe with vendor openai, links.analyze
   with default options, links.tag with tags [department:sales], links.diet.
   Line numbers refer to the worktree at the time of drawing.

   Attachments: add_tag (common/vcon.py:124) is the only writer a link calls.
   add_attachment (common/vcon.py:177) has no caller outside tests, and neither
   have add_party and add_dialog, so parties, dialog and any other attachment
   come from the producer.

   Lawful basis: no step here creates one. lawful_basis appears in non-test
   Python only in common/lib/vcon_compat.py, common/lib/vcon_egress_compat.py
   (comments) and common/storage/utopia/__init__.py (reads it). The entry drawn
   here is what a producer may send. Its dashed ring means it can be absent. */
(function () {
  'use strict';

  var LANE_TOKEN_Y = 22;
  var COLUMNS = { parties: 34, dialog: 164, analysis: 294, attachments: 464 };
  var ROWS = [186, 248, 310];
  var ENTRY_H = 54;

  /* ---------- Scene helpers, all safe to call on every frame ---------- */

  // Lane nodes before index are done, the node at index is active.
  function focusLane(ctx, index) {
    ctx.state.lane.forEach(function (node, i) {
      node.setState(i < index ? 'done' : (i === index ? 'active' : 'idle'));
    });
    ctx.state.laneEdges.forEach(function (edge) { edge.setState('idle'); });
  }

  // Moves the vCon token from above one lane node to above the next.
  function moveToken(ctx, from, to, p) {
    var lane = ctx.state.lane;
    var e = ctx.ease(p);
    ctx.state.token.at(ctx.lerp(lane[from].cx, lane[to].cx, e), LANE_TOKEN_Y);
    if (p < 1) { ctx.state.laneEdges[from].setState('active'); }
  }

  // Chain items before index are done, the item at index is active.
  function focusChain(ctx, index) {
    ctx.state.chain.forEach(function (item, i) {
      item.setState(i < index ? 'done' : (i === index ? 'active' : 'idle'));
    });
  }

  // Highlights the named entries in the card and clears the others.
  function highlight(ctx, names) {
    Object.keys(ctx.state.entries).forEach(function (name) {
      ctx.state.entries[name].setState(names.indexOf(name) >= 0 ? 'active' : 'idle');
    });
  }

  function detail(ctx, heading, body) {
    ctx.setText(ctx.state.detailHeading, heading);
    ctx.setText(ctx.state.detailBody, body);
  }

  // Flies a small card from a chain item into an entry slot, then fades it in.
  function deliver(ctx, p, itemIndex, entryName, label) {
    var s = ctx.state;
    var item = s.chain[itemIndex];
    var entry = s.entries[entryName];
    var t = ctx.ease(ctx.seg(p, 0, 0.7));
    s.fly.setLabel(label);
    s.fly.at(
      ctx.lerp(item.left[0], entry.cx, t),
      ctx.lerp(item.left[1], entry.cy, t)
    );
    ctx.show(s.fly, p < 0.75);
    ctx.fade(entry, ctx.seg(p, 0.6, 1));
  }

  function entry(ctx, column, row, width, label, sub) {
    return ctx.node({
      x: COLUMNS[column], y: ROWS[row], w: width, h: ENTRY_H, label: label, sub: sub
    });
  }

  VconMotion.register({
    id: 'm3',
    title: 'A vCon gains analysis, tags and attachments',
    summary: 'A vCon built by a producer runs a chain. Links add analysis and a tags attachment. Any lawful_basis attachment stays on the vCon with its body unchanged, and no step creates one.',
    twins: ['D07-vcon-lifecycle', 'D10-vcon-assembly'],

    setup: function (ctx) {
      var s = ctx.state;

      // D07 states on this path.
      s.lane = [
        { label: 'Producer', sub: 'outside this server' },
        { label: 'Id on an ingress list', sub: 'body cached in Redis' },
        { label: 'Running a chain', sub: 'one link at a time' },
        { label: 'Wrapping up', sub: 'egress, then storage' },
        { label: 'Saved', sub: 'body still in Redis' }
      ].map(function (item, i) {
        return ctx.node({ x: 20 + i * 189, y: 42, w: 164, h: 60, label: item.label, sub: item.sub });
      });
      s.laneEdges = [0, 1, 2, 3].map(function (i) {
        return ctx.edge({ from: s.lane[i].right, to: s.lane[i + 1].left });
      });

      // The vCon card, drawn behind the entries.
      ctx.el('rect', {
        x: 20, y: 118, width: 640, height: 392, rx: 6,
        fill: ctx.tokens.surface, stroke: ctx.tokens.muted, 'stroke-width': 1
      }, ctx.layers.back);
      ctx.el('line', {
        x1: 34, y1: 376, x2: 646, y2: 376, stroke: ctx.tokens.muted, 'stroke-width': 1
      }, ctx.layers.back);
      s.cardKey = ctx.text({ x: 34, y: 145, text: 'The vCon', kind: 'label' });
      s.version = ctx.text({ x: 646, y: 145, text: '', anchor: 'end' });
      Object.keys(COLUMNS).forEach(function (name) {
        ctx.text({ x: COLUMNS[name], y: 174, text: name, kind: 'title' });
      });

      // Entries start invisible and fade in on the step that adds them.
      s.entries = {
        party0: entry(ctx, 'parties', 0, 120, 'party 0', 'tel'),
        party1: entry(ctx, 'parties', 1, 120, 'party 1', 'mailto'),
        dialog0: entry(ctx, 'dialog', 0, 120, 'dialog 0', 'recording'),
        transcript: entry(ctx, 'analysis', 0, 160, 'transcript', 'dialog 0, vendor openai'),
        summary: entry(ctx, 'analysis', 1, 160, 'summary', 'dialog 0, from opts'),
        lawful: entry(ctx, 'attachments', 0, 182, 'lawful_basis', 'carried, never created'),
        tags: entry(ctx, 'attachments', 1, 182, 'tags', 'department:sales')
      };
      Object.keys(s.entries).forEach(function (name) { ctx.fade(s.entries[name], 0); });

      // Dashed ring: this entry is present only when the producer sent one.
      var lawful = s.entries.lawful;
      ctx.el('rect', {
        x: lawful.x - 5, y: lawful.y - 5, width: lawful.w + 10, height: lawful.h + 10,
        style: 'fill: none; stroke: ' + ctx.tokens.greenDeep + '; stroke-width: 1.5; stroke-dasharray: 6 4;'
      }, lawful.g);

      // A dashed box for the method no link calls.
      s.unused = entry(ctx, 'attachments', 2, 182, 'add_attachment()', 'no caller outside tests');
      s.unused.g.querySelector('rect').style.strokeDasharray = '6 4';
      ctx.fade(s.unused, 0);

      s.detailHeading = ctx.text({ x: 34, y: 402, text: '', kind: 'label' });
      s.detailBody = ctx.text({ x: 34, y: 428, text: '' });

      // Example chain and the storage call that follows it.
      ctx.text({ x: 680, y: 133, text: 'Example chain', kind: 'title' });
      s.chain = [
        { label: 'links.transcribe', sub: 'add_analysis()' },
        { label: 'links.analyze', sub: 'add_analysis()' },
        { label: 'links.tag', sub: 'add_tag()' },
        { label: 'links.diet', sub: 'optional filter' },
        { label: 'Storage.save(id)', sub: 'each chain storage' }
      ].map(function (item, i) {
        return ctx.node({ x: 680, y: 144 + i * 54, w: 260, h: 46, label: item.label, sub: item.sub });
      });

      ctx.el('rect', { x: 680, y: 430, width: 4, height: 72, fill: ctx.tokens.green }, ctx.layers.back);
      ctx.text({
        x: 696, y: 452, kind: 'label',
        text: 'No step here creates a lawful\nbasis or gates a chain on one.'
      });

      s.token = ctx.token({ x: s.lane[0].cx, y: LANE_TOKEN_Y, hidden: true });
      s.fly = ctx.token({ label: 'analysis', w: 92, hidden: true });
    },

    steps: [
      {
        // D10 UpstreamProducer to IngressPaths. api/api.py:750 post_vcon,
        // api/api.py:824 external_ingress_vcon, conserver/follower.py:46-50.
        // test: common/tests/test_api.py:113-138 posts a vCon holding a basis.
        id: 'producer-sends',
        label: 'A producer sends the vCon',
        caption: 'A producer outside the server builds the vCon and sends it. Parties and dialog come from the producer. It may also include a lawful_basis attachment. No server code creates one.',
        duration: 1400,
        draw: function (p, ctx) {
          var s = ctx.state;
          focusLane(ctx, 0);
          ctx.show(s.token, true);
          ctx.fade(s.token, ctx.seg(p, 0, 0.3));
          ['party0', 'party1', 'dialog0'].forEach(function (name) {
            ctx.fade(s.entries[name], ctx.seg(p, 0.1, 0.6));
          });
          ctx.fade(s.entries.lawful, ctx.seg(p, 0.5, 1));
          highlight(ctx, ['lawful']);
          ctx.setText(s.version, 'vcon: as sent');
          detail(ctx, 'What the producer sends',
            'parties, dialog and any attachments of its own.\nThe dashed ring marks an entry that may be absent.');
        }
      },
      {
        // D07 [*] to Queued, POST /vcon with ingress_lists.
        // api/api.py:789 cache_vcon_in_redis, api/api.py:450-452 sets
        // VCON_REDIS_EXPIRY with no _enforce_spec_on_write pass.
        // api/api.py:395 attachments is List[Dict], so entries get no check.
        // api/api.py:806 enqueue_async. conserver/follower.py:49-50 also writes
        // and enqueues, with no TTL on a new key. Without ingress_lists the id stays off any
        // queue: that is the D07 Cached state, left out of this path.
        id: 'server-caches',
        label: 'The server caches the body',
        caption: 'The API writes the body to Redis after model validation and pushes the id onto an ingress list. Attachments are plain dicts here, so nothing checks a lawful_basis body.',
        duration: 1300,
        draw: function (p, ctx) {
          var s = ctx.state;
          focusLane(ctx, p >= 1 ? 1 : 0);
          moveToken(ctx, 0, 1, p);
          highlight(ctx, []);
          ctx.setText(s.cardKey, 'vcon:<uuid> in Redis');
          detail(ctx, 'What the API checks',
            'Parties and dialog pass through their API models.\nThe API sets the key to expire after VCON_REDIS_EXPIRY.');
        }
      },
      {
        // D07 Queued to Running. conserver/main.py:875 queue.dequeue,
        // conserver/main.py:232 VconChainRequest.process,
        // conserver/main.py:603 module.run(vcon_id, link_name, options).
        // Read path: common/lib/vcon_redis.py:168 get_vcon,
        // common/lib/vcon_redis.py:223 normalize_legacy_fields,
        // common/lib/vcon_compat.py:63-75 renames type only if purpose is absent.
        id: 'worker-starts',
        label: 'A worker starts the chain',
        caption: 'A worker pops the id and runs the chain. Each link gets the id and loads the body through VconRedis. That read renames a legacy attachment type to purpose and keeps the body.',
        duration: 1300,
        draw: function (p, ctx) {
          focusLane(ctx, p >= 1 ? 2 : 1);
          moveToken(ctx, 1, 2, p);
          highlight(ctx, ['lawful']);
          detail(ctx, 'What a read changes',
            'normalize_legacy_fields renames legacy field names.\nIt leaves an attachment body alone.');
        }
      },
      {
        // conserver/links/transcribe/__init__.py:146-150 hands off to the vendor
        // module. conserver/links/openai_transcribe/__init__.py:582 add_analysis
        // with type transcript, vendor openai. common/vcon.py:209 add_analysis.
        // Write path: common/lib/vcon_redis.py:98 store_vcon,
        // common/lib/vcon_redis.py:61 _enforce_spec_on_write stamps 0.4.0,
        // common/redis_mgr.py:53-57 json_set with keepttl=True when ttl is None.
        id: 'transcribe-adds',
        label: 'Transcribe adds a transcript',
        caption: 'With vendor openai, the transcribe link hands off to its vendor module. That module calls add_analysis for each dialog and then store_vcon. The write stamps vcon 0.4.0 and keeps the TTL.',
        duration: 1500,
        draw: function (p, ctx) {
          var s = ctx.state;
          focusLane(ctx, 2);
          focusChain(ctx, 0);
          deliver(ctx, p, 0, 'transcript', 'analysis');
          highlight(ctx, ['transcript']);
          ctx.setText(s.version, p >= 0.6 ? 'vcon: "0.4.0"' : 'vcon: as sent');
          detail(ctx, 'What add_analysis appends',
            'type: "transcript", dialog: 0, vendor: "openai", body, encoding');
        }
      },
      {
        // conserver/links/analyze/__init__.py:32 analysis_type default summary,
        // conserver/links/analyze/__init__.py:37-38 source transcript,
        // conserver/links/analyze/__init__.py:181-190 add_analysis,
        // conserver/links/analyze/__init__.py:191 store_vcon.
        id: 'analyze-adds',
        label: 'Analyze adds a summary',
        caption: 'The analyze link reads the transcript of each dialog and sends it to a model. It adds the answer with add_analysis, then calls store_vcon. The analysis_type option defaults to summary.',
        duration: 1500,
        draw: function (p, ctx) {
          focusLane(ctx, 2);
          focusChain(ctx, 1);
          deliver(ctx, p, 1, 'summary', 'analysis');
          highlight(ctx, ['summary']);
          detail(ctx, 'What add_analysis appends',
            'type: "summary", dialog: 0, vendor from options, body, encoding: "none"');
        }
      },
      {
        // conserver/links/tag/__init__.py:39 add_tag, :40 store_vcon.
        // common/vcon.py:124-146 add_tag. common/vcon.py:129 builds the entry
        // with no party, dialog or start, and common/vcon.py:145 stores the list
        // as a JSON string. common/lib/vcon_redis.py:50-58 leaves a string body
        // alone. common/vcon.py:177 add_attachment has no caller outside tests.
        id: 'tag-writes',
        label: 'The tag link writes the tags attachment',
        caption: 'add_tag creates one attachment with purpose tags, or extends the one already there. This is the only attachment a link adds. Vcon also has add_attachment, but no code outside tests calls it.',
        duration: 1500,
        draw: function (p, ctx) {
          var s = ctx.state;
          focusLane(ctx, 2);
          focusChain(ctx, 2);
          deliver(ctx, p, 2, 'tags', 'tag');
          ctx.fade(s.unused, ctx.seg(p, 0.7, 1));
          highlight(ctx, ['tags']);
          detail(ctx, 'What add_tag writes',
            'purpose: "tags", encoding: "json", body: "[\\"department:sales\\"]"\nThe body is a JSON string, and readers decode it.');
        }
      },
      {
        // conserver/links/diet/__init__.py:39 remove_attachment_types default [],
        // conserver/links/diet/__init__.py:203-208 filter on mime_type,
        // conserver/links/diet/__init__.py:199-200 remove_analysis, default false.
        // Diet is the only link that assigns to attachments.
        id: 'diet-filters',
        label: 'Diet filters the listed attachments',
        caption: 'An optional diet link drops attachments whose mime_type is in remove_attachment_types. The list is empty by default. A lawful_basis entry stays unless it carries a listed mime_type.',
        duration: 1200,
        draw: function (p, ctx) {
          var s = ctx.state;
          focusLane(ctx, 2);
          focusChain(ctx, 3);
          ctx.show(s.fly, false);
          highlight(ctx, p < 1 ? ['lawful', 'tags'] : ['lawful']);
          detail(ctx, 'What diet removes here',
            'Nothing in this run. Its options default to removing nothing.');
        }
      },
      {
        // D07 Running to WrapUp. conserver/main.py:273-274 the last link returned
        // an id, conserver/main.py:345 _wrap_up, conserver/main.py:366 egress
        // lists first, conserver/main.py:368-382 storages next.
        id: 'chain-wraps-up',
        label: 'The chain reaches its wrap up',
        caption: 'The last link returns the id, so the chain wraps up. The id goes to any egress lists first, where it can feed another chain. The chain storages run next.',
        duration: 1200,
        draw: function (p, ctx) {
          focusLane(ctx, p >= 1 ? 3 : 2);
          focusChain(ctx, p >= 1 ? 4 : 3);
          moveToken(ctx, 2, 3, p);
          highlight(ctx, []);
          detail(ctx, 'What stays on the vCon',
            'Each entry added above, and any lawful_basis entry the producer sent.');
        }
      },
      {
        // D07 WrapUp to Stored. conserver/main.py:410 Storage(name).save(id),
        // common/storage/base.py:64-65. A save that raises goes to
        // conserver/main.py:429 _dead_letter_storage, shown in M4.
        // Egress: common/lib/vcon_egress_compat.py:152 to_configured_legacy,
        // common/lib/vcon_egress_compat.py:99-107 renames purpose to type,
        // common/lib/vcon_egress_compat.py:72-96 flips encoding json to none,
        // common/settings.py:74 EGRESS_FORMAT_VERSION. Callers:
        // common/storage/postgres/__init__.py:126, common/storage/s3/__init__.py:92,
        // common/storage/elasticsearch/__init__.py:73,
        // conserver/links/webhook/__init__.py:42, api/api.py:631, api/api.py:668.
        id: 'storage-saves',
        label: 'Each storage saves the vCon',
        caption: 'Each storage in the chain gets the id through Storage.save. With EGRESS_FORMAT_VERSION set, postgres, s3, elasticsearch, the webhook link and API reads send a 0.0.1 copy. The copy renames purpose to type and keeps the body value.',
        duration: 1400,
        draw: function (p, ctx) {
          focusLane(ctx, p >= 1 ? 4 : 3);
          focusChain(ctx, 4);
          moveToken(ctx, 3, 4, p);
          highlight(ctx, ['lawful']);
          detail(ctx, 'What a 0.0.1 egress copy holds',
            'type: "lawful_basis", the same body value, encoding: "none"\nThe copy in Redis stays at 0.4.0 with purpose.');
        }
      },
      {
        // common/storage/utopia/__init__.py:156-184 _lawful_basis reads the entry,
        // :184 returns the none recorded sentence, :251-252 adds it to the text,
        // :52 require_analysis_grant defaults to False, :327-329 skips the upload.
        // Edition boundary: the adapter option reads a basis and manages nothing.
        id: 'utopia-renders',
        label: 'Utopia renders an existing basis',
        caption: 'If the chain uses the utopia adapter, it reads the attachment and prints one sentence about it, or "Lawful basis: none recorded." With require_analysis_grant set, it skips the upload when no basis grants analysis. That option defaults to false. The server creates no basis and manages no consent.',
        duration: 1000,
        hold: 1500,
        draw: function (p, ctx) {
          var s = ctx.state;
          focusLane(ctx, 4);
          s.lane[4].setState('done');
          focusChain(ctx, 4);
          s.chain[4].setLabel('utopia adapter', 'reads and renders');
          highlight(ctx, ['lawful']);
          s.token.setState('done');
          detail(ctx, 'What the server leaves out',
            'It does not create a basis, or validate, enforce or manage consent.\nThat holds whether or not a basis arrived.');
        }
      }
    ]
  });
}());
