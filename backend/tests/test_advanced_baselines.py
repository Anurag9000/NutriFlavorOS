from backend.research.advanced_baselines import BM25Retriever, MatrixFactorizationRecommender, LinUCBPolicy, BetaBernoulliThompsonPolicy, BradleyTerryPreference, MahalanobisOOD, SplitConformalRegressor, KaplanMeierExpiry, InstructionDAGParser


def test_retrieval_and_recommendation_baselines_are_deterministic():
    bm=BM25Retriever().fit({"a":"lentil tomato soup","b":"chocolate cake"}); assert bm.search("lentil soup")[0][0]=="a"
    data=[("u1","r1",5),("u1","r2",1),("u2","r1",4),("u2","r2",2)]
    one=MatrixFactorizationRecommender(seed=7,epochs=10).fit(data); two=MatrixFactorizationRecommender(seed=7,epochs=10).fit(data)
    assert one.recommend("u1")==two.recommend("u1")


def test_bandit_and_preference_contracts():
    policy=LinUCBPolicy(["a","b"],2,alpha=0); policy.update("a",[1,0],1); assert policy.select([1,0])[0]=="a"
    th=BetaBernoulliThompsonPolicy(["a"],seed=1); assert th.select()[0]=="a"; th.update("a",1)
    btl=BradleyTerryPreference(epochs=30).fit([("a","b",1)]*5); assert btl.probability("a","b")>.5


def test_ood_conformal_survival_and_instruction_baselines():
    ood=MahalanobisOOD().fit([[0,0],[0.1,0],[0,0.1],[-0.1,0]]); assert ood.score([[5,5]])[0]>ood.score([[0,0]])[0]
    conformal=SplitConformalRegressor().fit([1,2,3],[1.1,1.9,3.2],alpha=.2); low,high=conformal.interval([2])[0]; assert low<2<high
    km=KaplanMeierExpiry().fit([1,2,3],[True,False,True]); assert 0<=km.survival_probability(3)<=1
    steps=InstructionDAGParser().parse(["Chop onion and heat oil","Add onion and stir"]); assert steps[1].dependencies==(0,) and "stir" in steps[1].actions
