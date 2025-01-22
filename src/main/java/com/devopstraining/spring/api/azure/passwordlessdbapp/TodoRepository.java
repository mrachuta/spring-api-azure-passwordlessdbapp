package com.devopstraining.spring.api.azure.passwordlessdbapp;

import org.springframework.data.repository.CrudRepository;

public interface TodoRepository extends CrudRepository<Todo, Long> {
}