"""Additional reproducible baselines for recommendation, uncertainty, and policy research.

These implementations are intentionally small, deterministic, and offline. They
provide auditable comparison points; they are not substitutes for validated
production models or medical decision systems.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import log, sqrt
import re
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple
import numpy as np


def _tokens(value: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


class BM25Retriever:
    def __init__(self, *, k1: float = 1.5, b: float = 0.75):
        if k1 <= 0 or not 0 <= b <= 1: raise ValueError("invalid BM25 parameters")
        self.k1=k1; self.b=b; self.ids:List[str]=[]; self.docs:List[List[str]]=[]; self.df:Dict[str,int]={}; self.avgdl=0.0
    def fit(self, documents: Mapping[str,str]) -> "BM25Retriever":
        self.ids=sorted(documents); self.docs=[_tokens(documents[i]) for i in self.ids]; self.avgdl=sum(map(len,self.docs))/max(1,len(self.docs)); self.df={}
        for doc in self.docs:
            for term in set(doc): self.df[term]=self.df.get(term,0)+1
        return self
    def search(self, query: str, *, k: int = 10) -> List[Tuple[str,float]]:
        if k<1: raise ValueError("k must be positive")
        n=len(self.docs); terms=_tokens(query); result=[]
        for identifier,doc in zip(self.ids,self.docs):
            counts={t:doc.count(t) for t in set(terms)}; score=0.0
            for term in terms:
                tf=counts.get(term,0); df=self.df.get(term,0); idf=log(1+(n-df+0.5)/(df+0.5)) if n else 0
                denominator=tf+self.k1*(1-self.b+self.b*len(doc)/max(self.avgdl,1e-12)); score+=idf*(tf*(self.k1+1)/denominator if denominator else 0)
            result.append((identifier,score))
        return sorted(result,key=lambda x:(-x[1],x[0]))[:k]


class MatrixFactorizationRecommender:
    def __init__(self, *, factors:int=16, learning_rate:float=0.03, regularization:float=0.02, epochs:int=50, seed:int=0):
        if factors<1 or epochs<1 or learning_rate<=0 or regularization<0: raise ValueError("invalid matrix-factorization parameters")
        self.factors=factors; self.lr=learning_rate; self.reg=regularization; self.epochs=epochs; self.seed=seed
    def fit(self, interactions: Sequence[Tuple[str,str,float]]) -> "MatrixFactorizationRecommender":
        if not interactions: raise ValueError("interactions are required")
        self.users=sorted({u for u,_,_ in interactions}); self.items=sorted({i for _,i,_ in interactions}); self.ui={u:n for n,u in enumerate(self.users)}; self.ii={i:n for n,i in enumerate(self.items)}
        rng=np.random.default_rng(self.seed); self.global_mean=float(np.mean([r for _,_,r in interactions])); self.p=rng.normal(0,0.1,(len(self.users),self.factors)); self.q=rng.normal(0,0.1,(len(self.items),self.factors)); self.ub=np.zeros(len(self.users)); self.ib=np.zeros(len(self.items))
        ordered=sorted(interactions,key=lambda x:(x[0],x[1],x[2]))
        for _ in range(self.epochs):
            for user,item,rating in ordered:
                u=self.ui[user]; i=self.ii[item]; pred=self.global_mean+self.ub[u]+self.ib[i]+float(self.p[u]@self.q[i]); error=float(rating)-pred; pu=self.p[u].copy()
                self.ub[u]+=self.lr*(error-self.reg*self.ub[u]); self.ib[i]+=self.lr*(error-self.reg*self.ib[i]); self.p[u]+=self.lr*(error*self.q[i]-self.reg*self.p[u]); self.q[i]+=self.lr*(error*pu-self.reg*self.q[i])
        return self
    def predict(self,user:str,item:str)->float:
        if user not in self.ui or item not in self.ii: return self.global_mean
        u=self.ui[user]; i=self.ii[item]; return float(self.global_mean+self.ub[u]+self.ib[i]+self.p[u]@self.q[i])
    def recommend(self,user:str,*,k:int=10,exclude:Iterable[str]=())->List[Tuple[str,float]]:
        banned=set(exclude); values=[(item,self.predict(user,item)) for item in self.items if item not in banned]; return sorted(values,key=lambda x:(-x[1],x[0]))[:k]


class LinUCBPolicy:
    def __init__(self, action_ids:Sequence[str], feature_dim:int, *, alpha:float=1.0):
        if not action_ids or feature_dim<1 or alpha<0: raise ValueError("invalid LinUCB configuration")
        self.actions=tuple(sorted(set(action_ids))); self.d=feature_dim; self.alpha=alpha; self.A={a:np.eye(feature_dim) for a in self.actions}; self.b={a:np.zeros(feature_dim) for a in self.actions}
    def select(self, context:Sequence[float], *, allowed:Iterable[str]|None=None)->Tuple[str,Dict[str,float]]:
        x=np.asarray(context,dtype=float)
        if x.shape!=(self.d,): raise ValueError("context dimension mismatch")
        candidates=self.actions if allowed is None else tuple(sorted(set(allowed)&set(self.actions)))
        if not candidates: raise ValueError("no allowed actions")
        scores={}
        for action in candidates:
            inv=np.linalg.inv(self.A[action]); theta=inv@self.b[action]; scores[action]=float(theta@x+self.alpha*sqrt(max(0,float(x@inv@x))))
        chosen=min(candidates,key=lambda a:(-scores[a],a)); return chosen,scores
    def update(self,action:str,context:Sequence[float],reward:float)->None:
        if action not in self.A: raise KeyError(action)
        x=np.asarray(context,dtype=float)
        if x.shape!=(self.d,): raise ValueError("context dimension mismatch")
        self.A[action]+=np.outer(x,x); self.b[action]+=float(reward)*x


class BetaBernoulliThompsonPolicy:
    def __init__(self, action_ids:Sequence[str], *, seed:int=0):
        if not action_ids: raise ValueError("actions are required")
        self.actions=tuple(sorted(set(action_ids))); self.success={a:1.0 for a in self.actions}; self.failure={a:1.0 for a in self.actions}; self.rng=np.random.default_rng(seed)
    def select(self, *, allowed:Iterable[str]|None=None)->Tuple[str,Dict[str,float]]:
        candidates=self.actions if allowed is None else tuple(sorted(set(allowed)&set(self.actions)))
        if not candidates: raise ValueError("no allowed actions")
        samples={a:float(self.rng.beta(self.success[a],self.failure[a])) for a in candidates}; return min(candidates,key=lambda a:(-samples[a],a)),samples
    def update(self,action:str,reward:float)->None:
        if action not in self.success: raise KeyError(action)
        if not 0<=reward<=1: raise ValueError("Bernoulli reward must be in [0,1]")
        self.success[action]+=reward; self.failure[action]+=1-reward


class BradleyTerryPreference:
    def __init__(self, *, learning_rate:float=0.05, epochs:int=200, regularization:float=0.01): self.lr=learning_rate; self.epochs=epochs; self.reg=regularization
    def fit(self, comparisons:Sequence[Tuple[str,str,float]])->"BradleyTerryPreference":
        if not comparisons: raise ValueError("comparisons are required")
        self.items=sorted({x for a,b,_ in comparisons for x in (a,b)}); self.score={x:0.0 for x in self.items}
        for _ in range(self.epochs):
            for a,b,outcome in sorted(comparisons):
                if not 0<=outcome<=1: raise ValueError("outcome must be in [0,1]")
                delta=np.clip(self.score[a]-self.score[b],-30,30); prob=float(1/(1+np.exp(-delta))); grad=outcome-prob
                self.score[a]+=self.lr*(grad-self.reg*self.score[a]); self.score[b]+=self.lr*(-grad-self.reg*self.score[b])
        mean=float(np.mean(list(self.score.values()))); self.score={k:v-mean for k,v in self.score.items()}; return self
    def probability(self,a:str,b:str)->float:
        delta=np.clip(self.score.get(a,0)-self.score.get(b,0),-30,30); return float(1/(1+np.exp(-delta)))
    def ranking(self)->List[Tuple[str,float]]: return sorted(self.score.items(),key=lambda x:(-x[1],x[0]))


class MahalanobisOOD:
    def __init__(self, *, regularization:float=1e-6): self.reg=regularization
    def fit(self, values:Sequence[Sequence[float]])->"MahalanobisOOD":
        x=np.asarray(values,dtype=float)
        if x.ndim!=2 or len(x)<2: raise ValueError("at least two vector samples are required")
        self.mean=x.mean(axis=0); covariance=np.cov(x,rowvar=False); covariance=np.atleast_2d(covariance)+np.eye(x.shape[1])*self.reg; self.precision=np.linalg.pinv(covariance); return self
    def score(self, values:Sequence[Sequence[float]])->List[float]:
        x=np.asarray(values,dtype=float); x=np.atleast_2d(x)
        if x.shape[1]!=len(self.mean): raise ValueError("feature dimension mismatch")
        return [float(np.sqrt(max(0,row@self.precision@row))) for row in x-self.mean]
    def threshold(self, calibration:Sequence[Sequence[float]], *, quantile:float=0.95)->float:
        if not 0<quantile<1: raise ValueError("quantile must be in (0,1)")
        return float(np.quantile(self.score(calibration),quantile,method="higher"))


class SplitConformalRegressor:
    def fit(self, predictions:Sequence[float], targets:Sequence[float], *, alpha:float=0.1)->"SplitConformalRegressor":
        if len(predictions)!=len(targets) or not predictions: raise ValueError("equal non-empty calibration arrays required")
        if not 0<alpha<1: raise ValueError("alpha must be in (0,1)")
        residuals=np.sort(np.abs(np.asarray(targets,dtype=float)-np.asarray(predictions,dtype=float))); rank=min(len(residuals)-1,int(np.ceil((len(residuals)+1)*(1-alpha)))-1); self.radius=float(residuals[max(0,rank)]); self.alpha=alpha; return self
    def interval(self,predictions:Sequence[float])->List[Tuple[float,float]]: return [(float(x-self.radius),float(x+self.radius)) for x in predictions]


@dataclass(frozen=True)
class SurvivalPoint: time:float; survival:float; at_risk:int; events:int
class KaplanMeierExpiry:
    def fit(self,durations:Sequence[float],events:Sequence[bool])->"KaplanMeierExpiry":
        if len(durations)!=len(events) or not durations: raise ValueError("equal non-empty arrays required")
        if any(x<0 for x in durations): raise ValueError("durations must be nonnegative")
        pairs=sorted(zip(map(float,durations),map(bool,events))); survival=1.0; points=[]
        for time in sorted({t for t,e in pairs if e}):
            at_risk=sum(t>=time for t,_ in pairs); occurred=sum(t==time and e for t,e in pairs); survival*=1-occurred/at_risk; points.append(SurvivalPoint(time,survival,at_risk,occurred))
        self.points=points; return self
    def survival_probability(self,time:float)->float:
        value=1.0
        for point in self.points:
            if point.time>time: break
            value=point.survival
        return value


@dataclass(frozen=True)
class InstructionStep: index:int; text:str; actions:Tuple[str,...]; dependencies:Tuple[int,...]
class InstructionDAGParser:
    ACTIONS=("add","bake","blend","boil","chill","combine","cook","drain","fold","fry","heat","mix","pour","preheat","rest","roast","serve","stir","transfer","whisk")
    def parse(self,instructions:Sequence[str])->List[InstructionStep]:
        steps=[]
        for index,text in enumerate(instructions):
            clean=" ".join(str(text).split()); tokens=set(_tokens(clean)); actions=tuple(a for a in self.ACTIONS if a in tokens); dependencies=() if index==0 else (index-1,)
            steps.append(InstructionStep(index,clean,actions,dependencies))
        return steps
