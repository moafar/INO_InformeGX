-- Rename only the current test accounts; historical actor usernames remain immutable.

UPDATE ergo_app.users
   SET username = 'fisioterapeuta_test',
       full_name = 'Fisioterapeuta Test'
 WHERE username = 'auxiliar_test'
   AND role = 'AUXILIAR';

UPDATE ergo_app.users
   SET full_name = 'Médico Test'
 WHERE username = 'medico_test'
   AND role = 'MEDICO';

UPDATE ergo_app.users
   SET username = 'lider_test',
       full_name = 'Líder Test'
 WHERE username = 'coordinadora_test'
   AND role = 'COORDINADORA';
