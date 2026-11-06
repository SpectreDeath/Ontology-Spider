% ==============================================================================
% Ontology-Spider Prolog Rule Library
% Provides transitive traversal, ancestry, recommendations, and proof-traces.
% ==============================================================================

:- dynamic triple/4.
:- dynamic attribute/3.

% ------------------------------------------------------------------------------
% BFS Transitive closure with visited-node cycle guard and proof tracing
% transitive_path(+Start, +Predicate, -End, -Path, -RulesFired, -FactIds)
% ------------------------------------------------------------------------------

transitive_path(Start, Predicate, End, Path, [transitive_closure], FactIds) :-
    bfs_transitive_all(Start, Predicate, AllAnswers),
    member(ans(End, Path, FactIds), AllAnswers).

bfs_transitive_all(Start, Predicate, AllAnswers) :-
    bfs_transitive_loop([q(Start, [Start], [])], [Start], Predicate, [], AllAnswers).

bfs_transitive_loop([], _Visited, _Predicate, Acc, Acc).
bfs_transitive_loop([q(Curr, RevPath, RevFactIds) | RestQueue], Visited, Predicate, Acc, AllAnswers) :-
    findall(
        cand(Next, AsrtId),
        ( triple(Curr, Predicate, Next, AsrtId),
          \+ member(Next, Visited) ),
        Candidates
    ),
    filter_candidates(Candidates, RevPath, RevFactIds, Visited, NewQueue, NewAnswers, UpdatedVisited),
    append(RestQueue, NewQueue, NextQueue),
    append(Acc, NewAnswers, NextAcc),
    bfs_transitive_loop(NextQueue, UpdatedVisited, Predicate, NextAcc, AllAnswers).

% ------------------------------------------------------------------------------
% BFS Ancestry (subclass_of and instance_of hierarchy)
% ancestor_of(+Entity, -Ancestor, -Path, -RulesFired, -FactIds)
% ------------------------------------------------------------------------------

ancestor_of(Entity, Ancestor, Path, [ancestor_rule], FactIds) :-
    bfs_ancestors_all(Entity, AllAnswers),
    member(ans(Ancestor, Path, FactIds), AllAnswers).

bfs_ancestors_all(Start, AllAnswers) :-
    bfs_ancestors_loop([q(Start, [Start], [])], [Start], [], AllAnswers).

bfs_ancestors_loop([], _Visited, Acc, Acc).
bfs_ancestors_loop([q(Curr, RevPath, RevFactIds) | RestQueue], Visited, Acc, AllAnswers) :-
    findall(
        cand(Next, AsrtId),
        ( triple(Curr, Pred, Next, AsrtId),
          ( Pred = subclass_of ; Pred = instance_of ),
          \+ member(Next, Visited) ),
        Candidates
    ),
    filter_candidates(Candidates, RevPath, RevFactIds, Visited, NewQueue, NewAnswers, UpdatedVisited),
    append(RestQueue, NewQueue, NextQueue),
    append(Acc, NewAnswers, NextAcc),
    bfs_ancestors_loop(NextQueue, UpdatedVisited, NextAcc, AllAnswers).

% Shared BFS helper for filtering candidates and building queue and answers
filter_candidates([], _RevPath, _RevFactIds, Visited, [], [], Visited).
filter_candidates([cand(Next, AsrtId) | Rest], RevPath, RevFactIds, Visited, QueueOut, AnsOut, FinalVisited) :-
    ( member(Next, Visited) ->
        filter_candidates(Rest, RevPath, RevFactIds, Visited, QueueOut, AnsOut, FinalVisited)
    ;
        reverse([Next | RevPath], Path),
        reverse([AsrtId | RevFactIds], FactIds),
        filter_candidates(Rest, RevPath, RevFactIds, [Next | Visited], RestQueue, RestAns, FinalVisited),
        QueueOut = [q(Next, [Next | RevPath], [AsrtId | RevFactIds]) | RestQueue],
        AnsOut = [ans(Next, Path, FactIds) | RestAns]
    ).

% ------------------------------------------------------------------------------
% Subclass closure: reflexive transitive closure over subclass_of
% subclass_closure(+TargetClass, -AncestorClass, -FactIds)
% ------------------------------------------------------------------------------

subclass_closure(Class, Class, []).
subclass_closure(Class, Super, [AsrtId | Rest]) :-
    triple(Class, subclass_of, Next, AsrtId),
    subclass_closure(Next, Super, Rest).

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

% ------------------------------------------------------------------------------
% Deliberately non-terminating rule for testing timeout guards (left-recursive)
% ------------------------------------------------------------------------------

infinite_loop :-
    infinite_loop.
