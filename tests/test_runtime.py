"""Tests for nous.runtime — Agent ABC, NousRuntime, Hippocampus, MessageBus."""
import sys

import numpy as np
import pytest

from nous.runtime import (
    Agent, AgentResult, NousRuntime, Hippocampus, MessageBus, Message,
)


class _AddOne(Agent):
    """Trivial agent: returns task + 1."""
    NAME = 'add_one'

    def _think(self, task, context):
        return task + 1


class _Echo(Agent):
    NAME = 'echo'

    def _think(self, task, context):
        return {'task': task, 'ctx_keys': list(context.keys())}


class _Boom(Agent):
    NAME = 'boom'

    def _think(self, task, context):
        raise RuntimeError('intentional')


class TestAgent:
    def test_basic_execute(self):
        a = _AddOne()
        r = a.execute(5)
        assert r.ok
        assert r.output == 6
        assert r.agent == 'add_one'

    def test_error_capture(self):
        a = _Boom()
        r = a.execute('x')
        assert not r.ok
        assert 'RuntimeError' in r.error

    def test_latency_recorded(self):
        a = _AddOne()
        r = a.execute(1)
        assert r.latency_ms >= 0


class TestRuntime:
    def test_register_dispatch(self):
        rt = NousRuntime()
        rt.register(_AddOne())
        rt.register(_Echo())
        r1 = rt.dispatch('add_one', 10)
        assert r1.output == 11
        r2 = rt.dispatch('echo', 'hello')
        assert r2.output['task'] == 'hello'

    def test_unknown_agent_raises(self):
        rt = NousRuntime()
        with pytest.raises(KeyError):
            rt.dispatch('nope', None)

    def test_pipeline_propagates_outputs(self):
        rt = NousRuntime()
        rt.register(_AddOne())
        rt.register(_Echo())
        results = rt.pipeline([
            ('add_one', 1),
            ('echo', 'check'),
        ])
        assert len(results) == 2
        assert results[0].output == 2
        # Echo should see the prior output in its context
        assert 'output_add_one' in results[1].output['ctx_keys']
        assert 'latest_output' in results[1].output['ctx_keys']

    def test_health_all(self):
        rt = NousRuntime()
        rt.register(_AddOne())
        h = rt.health_all()
        assert h['n_agents'] == 1
        assert h['agents'][0]['name'] == 'add_one'


class TestHippocampus:
    def test_store_recall(self):
        h = Hippocampus(H=8, W=8)
        s = np.zeros((8, 8))
        s[2:5, 2:5] = 1.0
        h.store('a', s)
        rec = h.recall('a', s)
        assert rec.shape == (8, 8)
        c = np.corrcoef(s.flatten(), rec.flatten())[0, 1]
        assert c > 0.5

    def test_capacity_estimate(self):
        h = Hippocampus(H=16, W=16)
        assert h.capacity_estimate == int(0.14 * 256)


class TestMessageBus:
    def test_pub_sub(self):
        bus = MessageBus()
        bus.subscribe('B', 'ch1')
        bus.publish('ch1', 'hi', sender='A')
        msgs = bus.drain_for('B')
        assert len(msgs) == 1
        assert msgs[0].payload == 'hi'
        assert msgs[0].sender == 'A'
