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
