% ==============================================================================
% Ontology-Spider Prolog Rule Library
% Provides transitive traversal, ancestry, recommendations, and proof-traces.
% ==============================================================================

:- use_module(library(assoc)).

:- dynamic triple/4.
:- dynamic attribute/3.

prepend_reversed([], Acc, Acc).
prepend_reversed([H | T], Acc, Out) :-
    prepend_reversed(T, [H | Acc], Out).

% ------------------------------------------------------------------------------
% BFS Transitive closure with visited-node cycle guard and proof tracing
% transitive_path(+Start, +Predicate, -End, -Path, -RulesFired, -FactIds)
% ------------------------------------------------------------------------------

transitive_path(Start, Predicate, End, Path, [transitive_closure], FactIds) :-
    bfs_transitive_all(Start, Predicate, AllAnswers),
    member(ans(End, Path, FactIds), AllAnswers).

bfs_transitive_all(Start, Predicate, AllAnswers) :-
    empty_assoc(Empty),
    put_assoc(Start, Empty, true, Visited0),
    bfs_transitive_loop([q(Start, [Start], [])], [], Visited0, Predicate, [], AllAnswers).

bfs_transitive_loop([], [], _Visited, _Predicate, RevAcc, AllAnswers) :-
    reverse(RevAcc, AllAnswers).
bfs_transitive_loop([], Back, Visited, Predicate, RevAcc, AllAnswers) :-
    Back \= [],
    reverse(Back, NewFront),
    bfs_transitive_loop(NewFront, [], Visited, Predicate, RevAcc, AllAnswers).
bfs_transitive_loop([q(Curr, RevPath, RevFactIds) | RestFront], Back, Visited, Predicate, RevAcc, AllAnswers) :-
    findall(
        cand(Next, AsrtId),
        ( triple(Curr, Predicate, Next, AsrtId),
          \+ get_assoc(Next, Visited, _) ),
        Candidates
    ),
    filter_candidates(Candidates, RevPath, RevFactIds, Visited, NewQueue, NewAnswers, UpdatedVisited),
    prepend_reversed(NewQueue, Back, NextBack),
    prepend_reversed(NewAnswers, RevAcc, NextRevAcc),
    bfs_transitive_loop(RestFront, NextBack, UpdatedVisited, Predicate, NextRevAcc, AllAnswers).

% ------------------------------------------------------------------------------
% BFS Ancestry (subclass_of and instance_of hierarchy)
% ancestor_of(+Entity, -Ancestor, -Path, -RulesFired, -FactIds)
% ------------------------------------------------------------------------------

ancestor_of(Entity, Ancestor, Path, [ancestor_rule], FactIds) :-
    bfs_ancestors_all(Entity, AllAnswers),
    member(ans(Ancestor, Path, FactIds), AllAnswers).

bfs_ancestors_all(Start, AllAnswers) :-
    empty_assoc(Empty),
    put_assoc(Start, Empty, true, Visited0),
    bfs_ancestors_loop([q(Start, [Start], [])], [], Visited0, [], AllAnswers).

bfs_ancestors_loop([], [], _Visited, RevAcc, AllAnswers) :-
    reverse(RevAcc, AllAnswers).
bfs_ancestors_loop([], Back, Visited, RevAcc, AllAnswers) :-
    Back \= [],
    reverse(Back, NewFront),
    bfs_ancestors_loop(NewFront, [], Visited, RevAcc, AllAnswers).
bfs_ancestors_loop([q(Curr, RevPath, RevFactIds) | RestFront], Back, Visited, RevAcc, AllAnswers) :-
    findall(
        cand(Next, AsrtId),
        ( triple(Curr, Pred, Next, AsrtId),
          ( Pred = subclass_of ; Pred = instance_of ),
          \+ get_assoc(Next, Visited, _) ),
        Candidates
    ),
    filter_candidates(Candidates, RevPath, RevFactIds, Visited, NewQueue, NewAnswers, UpdatedVisited),
    prepend_reversed(NewQueue, Back, NextBack),
    prepend_reversed(NewAnswers, RevAcc, NextRevAcc),
    bfs_ancestors_loop(RestFront, NextBack, UpdatedVisited, NextRevAcc, AllAnswers).

% Shared BFS helper for filtering candidates and building queue and answers
filter_candidates([], _RevPath, _RevFactIds, Visited, [], [], Visited).
filter_candidates([cand(Next, AsrtId) | Rest], RevPath, RevFactIds, Visited, QueueOut, AnsOut, FinalVisited) :-
    ( get_assoc(Next, Visited, _) ->
        filter_candidates(Rest, RevPath, RevFactIds, Visited, QueueOut, AnsOut, FinalVisited)
    ;
        reverse([Next | RevPath], Path),
        reverse([AsrtId | RevFactIds], FactIds),
        put_assoc(Next, Visited, true, Visited1),
        filter_candidates(Rest, RevPath, RevFactIds, Visited1, RestQueue, RestAns, FinalVisited),
        QueueOut = [q(Next, [Next | RevPath], [AsrtId | RevFactIds]) | RestQueue],
        AnsOut = [ans(Next, Path, FactIds) | RestAns]
    ).

% ------------------------------------------------------------------------------
% Subclass closure: BFS reflexive transitive closure over subclass_of (cycle-safe)
% subclass_closure(?TargetClass, +AncestorClass, -FactIds)
% ------------------------------------------------------------------------------

subclass_closure(TargetClass, AncestorClass, FactIds) :-
    bfs_subclass_all(AncestorClass, AllSubclasses),
    member(sub(TargetClass, FactIds), AllSubclasses).

bfs_subclass_all(Start, AllSubclasses) :-
    empty_assoc(Empty),
    put_assoc(Start, Empty, true, Visited0),
    bfs_subclass_loop([sq(Start, [])], [], Visited0, [sub(Start, [])], AllSubclasses).

bfs_subclass_loop([], [], _Visited, RevAcc, AllSubclasses) :-
    reverse(RevAcc, AllSubclasses).
bfs_subclass_loop([], Back, Visited, RevAcc, AllSubclasses) :-
    Back \= [],
    reverse(Back, NewFront),
    bfs_subclass_loop(NewFront, [], Visited, RevAcc, AllSubclasses).
bfs_subclass_loop([sq(Curr, FactIds) | RestFront], Back, Visited, RevAcc, AllSubclasses) :-
    findall(
        scand(Child, AsrtId),
        ( triple(Child, subclass_of, Curr, AsrtId),
          \+ get_assoc(Child, Visited, _) ),
        Candidates
    ),
    filter_subclass_candidates(Candidates, FactIds, Visited, NewQueue, NewSubs, UpdatedVisited),
    prepend_reversed(NewQueue, Back, NextBack),
    prepend_reversed(NewSubs, RevAcc, NextRevAcc),
    bfs_subclass_loop(RestFront, NextBack, UpdatedVisited, NextRevAcc, AllSubclasses).

filter_subclass_candidates([], _FactIds, Visited, [], [], Visited).
filter_subclass_candidates([scand(Child, AsrtId) | Rest], FactIds, Visited, QueueOut, SubOut, FinalVisited) :-
    ( get_assoc(Child, Visited, _) ->
        filter_subclass_candidates(Rest, FactIds, Visited, QueueOut, SubOut, FinalVisited)
    ;
        NewFactIds = [AsrtId | FactIds],
        put_assoc(Child, Visited, true, Visited1),
        filter_subclass_candidates(Rest, FactIds, Visited1, RestQueue, RestSubs, FinalVisited),
        QueueOut = [sq(Child, NewFactIds) | RestQueue],
        SubOut = [sub(Child, NewFactIds) | RestSubs]
    ).

% ------------------------------------------------------------------------------
% Recommendations: Instances of Class across transitive subclass hierarchy
% matching all specified attributes
% ------------------------------------------------------------------------------

entity_has_attr(Entity, AsrtId, Key, Value) :-
    attribute(Entity, Key, Value),
    !.
entity_has_attr(_Entity, AsrtId, Key, Value) :-
    attribute(AsrtId, Key, Value),
    !.

matches_all_attrs(_Entity, _AsrtId, []).
matches_all_attrs(Entity, AsrtId, [Key=Value | Rest]) :-
    entity_has_attr(Entity, AsrtId, Key, Value),
    matches_all_attrs(Entity, AsrtId, Rest).

recommend_candidates(Class, AttrList, Candidate, RulesFired, FactIds) :-
    subclass_closure(TargetClass, Class, SubFacts),
    triple(Candidate, instance_of, TargetClass, AsrtId),
    matches_all_attrs(Candidate, AsrtId, AttrList),
    RulesFired = [recommend, instance_of_transitive, match_attribute],
    FactIds = [AsrtId | SubFacts].

% Deduplicated recommend query entrypoints
recommend(Class, Candidate, RulesFired, FactIds) :-
    recommend_candidates(Class, [], Candidate, RulesFired, FactIds).

recommend_match(Class, Key, Value, Candidate, RulesFired, FactIds) :-
    recommend_candidates(Class, [Key=Value], Candidate, RulesFired, FactIds).

recommend_multi(Class, AttrList, Candidate, RulesFired, FactIds) :-
    recommend_candidates(Class, AttrList, Candidate, RulesFired, FactIds).


% ------------------------------------------------------------------------------
% Attribute inference / matching
% ------------------------------------------------------------------------------

match_attribute(Entity, Key, Value, AsrtId) :-
    attribute(Entity, Key, Value),
    AsrtId = 'attr_match'.

filter_match(Predicate, Key, Value, Subj, Obj, AsrtId) :-
    triple(Subj, Predicate, Obj, AsrtId),
    entity_has_attr(Subj, AsrtId, Key, Value).

% ------------------------------------------------------------------------------
% Shortest path & closed-world negation
% ------------------------------------------------------------------------------

shortest_path_anc(Start, Start, [Start], []) :- !.
shortest_path_anc(Start, Target, Path, FactIds) :-
    bfs_ancestors_all(Start, All),
    member(ans(Target, Path, FactIds), All),
    !.

shortest_path_pred(Start, _Pred, Start, [Start], []) :- !.
shortest_path_pred(Start, Pred, Target, Path, FactIds) :-
    bfs_transitive_all(Start, Pred, All),
    member(ans(Target, Path, FactIds), All),
    !.

check_not_triple(S, P, O, false, [negation_refuted], [AsrtId], [S, O]) :-
    triple(S, P, O, AsrtId),
    !.
check_not_triple(S, _P, O, true, [closed_world_negation], [], [SLabel, OLabel]) :-
    ( var(S) -> SLabel = '*' ; SLabel = S ),
    ( var(O) -> OLabel = '*' ; OLabel = O ).

% ------------------------------------------------------------------------------
% Deliberately non-terminating rule for testing timeout guards (left-recursive)
% ------------------------------------------------------------------------------

infinite_loop :-
    infinite_loop.
