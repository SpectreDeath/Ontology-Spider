% ==============================================================================
% Ontology-Spider Prolog Rule Library
% Provides transitive traversal, ancestry, recommendations, and proof-traces.
% ==============================================================================

:- dynamic triple/4.
:- dynamic attribute/3.

% ------------------------------------------------------------------------------
% Transitive closure with visited-node cycle guard and proof tracing
% transitive_path(+Start, +Predicate, -End, -Path, -RulesFired, -FactIds)
% ------------------------------------------------------------------------------

transitive_path(Start, Predicate, End, Path, RulesFired, FactIds) :-
    transitive_step(Start, Predicate, End, [Start], RevPath, FactIds),
    reverse(RevPath, Path),
    RulesFired = [transitive_closure].

transitive_step(Current, Predicate, Next, Visited, [Next, Current | VisitedTail], [AsrtId]) :-
    triple(Current, Predicate, Next, AsrtId),
    \+ member(Next, Visited),
    Visited = [Current | VisitedTail].

transitive_step(Current, Predicate, End, Visited, FinalPath, [AsrtId | RestFactIds]) :-
    triple(Current, Predicate, Intermediate, AsrtId),
    \+ member(Intermediate, Visited),
    transitive_step(Intermediate, Predicate, End, [Intermediate | Visited], FinalPath, RestFactIds).

% ------------------------------------------------------------------------------
% Ancestry (subclass_of and instance_of hierarchy)
% ancestor_of(+Entity, -Ancestor, -Path, -RulesFired, -FactIds)
% ------------------------------------------------------------------------------

ancestor_of(Entity, Ancestor, Path, [ancestor_rule], FactIds) :-
    ancestor_step(Entity, Ancestor, [Entity], RevPath, FactIds),
    reverse(RevPath, Path).

ancestor_step(Current, Super, Visited, [Super, Current | VisitedTail], [AsrtId]) :-
    ( triple(Current, subclass_of, Super, AsrtId)
    ; triple(Current, instance_of, Super, AsrtId) ),
    \+ member(Super, Visited),
    Visited = [Current | VisitedTail].

ancestor_step(Current, Ancestor, Visited, FinalPath, [AsrtId | RestFactIds]) :-
    ( triple(Current, subclass_of, Next, AsrtId)
    ; triple(Current, instance_of, Next, AsrtId) ),
    \+ member(Next, Visited),
    ancestor_step(Next, Ancestor, [Next | Visited], FinalPath, RestFactIds).

% ------------------------------------------------------------------------------
% Recommendations: Shared category / domain inference
% recommend(+Item, -Recommendation, -SharedCategory, -RulesFired, -FactIds)
% ------------------------------------------------------------------------------

recommend(Item, Recommendation, SharedCategory, [recommend_shared_category], [Asrt1, Asrt2]) :-
    ( triple(Item, instance_of, SharedCategory, Asrt1)
    ; triple(Item, subclass_of, SharedCategory, Asrt1) ),
    ( triple(Recommendation, instance_of, SharedCategory, Asrt2)
    ; triple(Recommendation, subclass_of, SharedCategory, Asrt2) ),
    Item \= Recommendation.

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
    sleep(0.01),
    infinite_loop.
