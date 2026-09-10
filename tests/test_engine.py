import math
import numpy as np
import pandas as pd
import pytest

from ttp_similarity import config
from ttp_similarity.engine import (
    weighting,
    similarity,
    confidence,
    vectorize,
    query,
    rank_actors
)
from ttp_similarity.schema import (
    Candidate,
    ConfidenceBreakdown,
    ConfidenceLevel,
    QueryResult,
    TechniqueId,
    VectorSpace,
    SimilarityMatrix
)


# -- weighting.py tests --
def test_idf_monotonicity():
    s = config.IDF_SMOOTHING
    N = 100
    # Rarer (smaller df) -> heavier (larger idf)
    assert weighting.idf(10, N, s) > weighting.idf(50, N, s)

def test_idf_validation():
    with pytest.raises(ValueError):
        weighting.idf(-1, 10)
    with pytest.raises(ValueError):
        weighting.idf(5, 0)

def test_compute_weights():
    freq = pd.DataFrame({
        "technique_id": ["T1", "T2"],
        "technique_name": ["Name1", "Name2"],
        "actor_count": [10, 50],
        "actor_ratio": [0.1, 0.5]
    })
    
    # Binary
    w_bin = weighting.compute_weights(freq, 100, scheme="binary")
    assert all(w_bin["weight"] == 1.0)
    
    # Smooth IDF
    w_smooth = weighting.compute_weights(freq, 100, scheme="smooth_idf")
    assert w_smooth.loc[w_smooth["technique_id"] == "T1", "weight"].values[0] > w_smooth.loc[w_smooth["technique_id"] == "T2", "weight"].values[0]
    
def test_normalized_rarity():
    weights = {"T1": 10.0, "T2": 2.0, "T3": 5.0}
    
    # Empty inputs
    assert weighting.normalized_rarity([], weights) == 0.0
    assert weighting.normalized_rarity(["T1"], {}) == 0.0
    
    # Unknown ids get min weight (2.0)
    # T1=10, T2=2, T99=2 -> mean=14/3 = 4.666
    # max=10
    # result = 4.666 / 10 = 0.4666
    res = weighting.normalized_rarity(["T1", "T2", "T99"], weights)
    assert math.isclose(res, 0.466666, rel_tol=1e-4)

# -- confidence.py tests --
def test_margin_component():
    assert confidence.margin_component(0.0, 0.5) == 0.0
    assert confidence.margin_component(0.8, None) == 1.0
    
    # top=0.8, runner=0.6, gap=0.25. saturation=0.15 -> 0.25/0.15 > 1.0 -> 1.0
    assert confidence.margin_component(0.8, 0.6, saturation=0.15) == 1.0
    
    # top=0.8, runner=0.76, gap=0.05. saturation=0.15 -> 1/3
    assert math.isclose(confidence.margin_component(0.8, 0.76, saturation=0.15), 1/3, rel_tol=1e-4)

def test_sufficiency_component():
    assert confidence.sufficiency_component(2, minimum=3, saturation=12) == 0.0
    assert confidence.sufficiency_component(15, minimum=3, saturation=12) == 1.0
    assert math.isclose(confidence.sufficiency_component(7, minimum=3, saturation=12), 4/9, rel_tol=1e-4)

def test_score_confidence_empty():
    brk = confidence.score_confidence([], ["T1", "T2"], {"T1": 1.0})
    assert brk.level == ConfidenceLevel.LOW
    assert brk.score == 0.0

def test_score_confidence_low_override():
    # Only 2 known techniques, min is 3 -> force LOW
    cand = [
        Candidate(rank=1, actor_id="G1", actor_name="G1", score=0.9, matched_technique_ids=("T1", "T2")),
    ]
    brk = confidence.score_confidence(cand, ["T1", "T2"], {"T1": 5.0, "T2": 5.0})
    assert brk.level == ConfidenceLevel.LOW

# -- vectorize.py tests --
def test_vectorize_query():
    space = VectorSpace(
        actor_ids=("G1",),
        technique_ids=("T1", "T2", "T3"),
        matrix=np.array([[1.0, 1.0, 0.0]])
    )
    weights = {"T1": 2.0, "T2": 3.0, "T3": 4.0}
    
    vec, known, unknown = vectorize.vectorize_query(["T1", "T99", "T2"], space, weights, normalize=False)
    assert known == ("T1", "T2")
    assert unknown == ("T99",)
    assert vec[0] == 2.0
    assert vec[1] == 3.0
    assert vec[2] == 0.0

    # Test empty/unknown
    vec2, known2, unknown2 = vectorize.vectorize_query(["T99"], space, weights, normalize=True)
    assert len(known2) == 0
    assert unknown2 == ("T99",)
    assert np.all(vec2 == 0)

# -- similarity.py tests --
def test_cosine_similarity_matrix():
    space = VectorSpace(
        actor_ids=("G1", "G2", "G3"),
        technique_ids=("T1", "T2"),
        matrix=np.array([
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 0.0]
        ])
    )
    sim = similarity.cosine_similarity_matrix(space)
    assert sim.shape == (3, 3)
    assert sim[0, 0] == 1.0
    assert sim[0, 1] == 0.0
    assert sim[0, 2] == 1.0

# -- engine.__init__.py rank_actors integration --
def test_rank_actors_empty_mock(monkeypatch):
    # Instead of hitting the actual mock dataset, we can just run query CLI test or 
    # mock load_engine. Let's patch load_engine to provide a tiny space.
    import ttp_similarity.engine.loading as loading
    from ttp_similarity.schema import EngineArtifacts, Actor
    
    def fake_load_engine(dataset, with_similarity):
        space = VectorSpace(
            actor_ids=("G1", "G2"),
            technique_ids=("T1", "T2", "T3"),
            matrix=np.array([
                [0.8, 0.6, 0.0],
                [0.0, 1.0, 0.0]
            ])
        )
        return EngineArtifacts(
            dataset="test",
            actors=(Actor("G1", "Group 1", technique_ids=("T1", "T2")), Actor("G2", "Group 2", technique_ids=("T2",))),
            technique_names={"T1": "Tech 1", "T2": "Tech 2", "T3": "Tech 3"},
            weights={"T1": 5.0, "T2": 2.0, "T3": 4.0},
            space=space,
            similarity=None,
            clusters=None
        )
        
    monkeypatch.setattr(loading, "load_engine", fake_load_engine)
    
    res = rank_actors(["T99"])
    assert len(res) == 0  # No candidates returned for empty known query
    
    res = rank_actors(["T1", "T2"])
    assert len(res) == 2
    assert res[0]["actor_id"] == "G1"
    assert res[0]["match_count"] == 2
