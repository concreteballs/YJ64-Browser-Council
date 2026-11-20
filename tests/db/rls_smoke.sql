BEGIN;
SET ROLE browser_council_runtime;

SELECT set_config('app.user_id', '11111111-1111-4111-8111-111111111111', true);
INSERT INTO workspaces (id, name, created_by)
VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Tenant A', app.current_user_id());
INSERT INTO workspace_members (workspace_id, user_id, role)
VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', app.current_user_id(), 'owner');
INSERT INTO conversations (id, workspace_id, title, created_by)
VALUES (
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'Private conversation',
  app.current_user_id()
);

SELECT set_config('app.user_id', '22222222-2222-4222-8222-222222222222', true);

DO $$
DECLARE visible_rows integer;
BEGIN
  SELECT count(*) INTO visible_rows
  FROM conversations
  WHERE id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
  IF visible_rows <> 0 THEN
    RAISE EXCEPTION 'RLS FAILURE: foreign tenant conversation was visible';
  END IF;

  BEGIN
    INSERT INTO conversations (workspace_id, title, created_by)
    VALUES (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      'Unauthorized write',
      app.current_user_id()
    );
    RAISE EXCEPTION 'RLS FAILURE: foreign tenant insert unexpectedly succeeded';
  EXCEPTION
    WHEN insufficient_privilege THEN NULL;
  END;
END $$;

ROLLBACK;
