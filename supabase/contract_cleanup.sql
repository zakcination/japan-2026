-- removes the throwaway 'contract-test' trip created for python3 src/tests/group_contract.py
delete from public.member_events where member in (select id from public.members where trip = 'contract-test');
delete from public.attachments where member in (select id from public.members where trip = 'contract-test');
delete from public.my_stops where member in (select id from public.members where trip = 'contract-test');
delete from public.my_bookings where member in (select id from public.members where trip = 'contract-test');
delete from public.task_state where member in (select id from public.members where trip = 'contract-test');
delete from public.joins where member in (select id from public.members where trip = 'contract-test');
delete from public.member_devices where member in (select id from public.members where trip = 'contract-test');
delete from public.members where trip = 'contract-test';
delete from public.tasks where trip = 'contract-test';
delete from public.recipes where trip = 'contract-test';
delete from public.parts where trip = 'contract-test';
delete from public.plan where trip = 'contract-test';
delete from public.trips where id = 'contract-test';
